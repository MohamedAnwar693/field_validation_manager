import base64
import csv
import io
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ImportValidatorWizard(models.TransientModel):
    _name = 'import.validator.wizard'
    _description = 'Import Pre-Validator Wizard'

    state = fields.Selection([
        ('upload',   'Upload File'),
        ('mapping',  'Map Columns'),
        ('result',   'Validation Result'),
    ], string='Step', default='upload', readonly=True)

    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        domain=[('transient', '=', False)],
    )
    model_name = fields.Char(related='model_id.model')

    ruleset_id = fields.Many2one(
        'field.validation.ruleset',
        string='Rule Set (optional)',
        domain="[('model_id', '=', model_id)]",
        help='Leave empty to apply all active rules for the model.',
    )

    import_file = fields.Binary(
        string='Import File',
        attachment=False,
        help='Upload a CSV or Excel file to validate.',
    )
    import_filename = fields.Char(string='Filename')
    file_type = fields.Selection([
        ('csv',  'CSV'),
        ('xlsx', 'Excel (.xlsx)'),
    ], string='File Type', default='csv', required=True)
    csv_delimiter = fields.Char(string='CSV Delimiter', default=',')
    has_header = fields.Boolean(string='File Has Header Row', default=True)

    column_mapping_json = fields.Text(
        string='Column Mapping (JSON)',
        help='Internal: JSON mapping of column index to field name.',
    )
    column_mapping_display = fields.Text(
        string='Column → Field Mapping',
        compute='_compute_column_mapping_display',
    )

    result_summary = fields.Html(
        string='Validation Summary',
        readonly=True,
    )
    result_json = fields.Text(
        string='Full Results (JSON)',
        readonly=True,
    )
    log_id = fields.Many2one(
        'field.validation.log',
        string='Validation Log',
        readonly=True,
    )

    total_rows = fields.Integer(string='Total Rows', readonly=True)
    passed_rows = fields.Integer(string='Passed', readonly=True)
    error_rows = fields.Integer(string='With Errors', readonly=True)
    warning_rows = fields.Integer(string='With Warnings', readonly=True)

    @api.depends('column_mapping_json')
    def _compute_column_mapping_display(self):
        for rec in self:
            if rec.column_mapping_json:
                try:
                    mapping = json.loads(rec.column_mapping_json)
                    lines = [f'Column {k}: → {v}' for k, v in mapping.items()]
                    rec.column_mapping_display = '\n'.join(lines)
                except Exception:
                    rec.column_mapping_display = rec.column_mapping_json
            else:
                rec.column_mapping_display = ''

    def action_parse_file(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_('Please upload a file first.'))

        rows = self._parse_file()
        if not rows:
            raise UserError(_('The file appears to be empty or could not be parsed.'))

        model_fields = self.env['ir.model.fields'].search([
            ('model_id', '=', self.model_id.id),
            ('ttype', 'not in', ['one2many', 'many2many', 'binary']),
        ])
        field_by_name = {f.name: f for f in model_fields}
        field_by_label = {f.field_description.lower(): f for f in model_fields}

        if self.has_header and rows:
            headers = rows[0]
            mapping = {}
            for i, col in enumerate(headers):
                col_clean = str(col).strip().lower()
                if col_clean in field_by_name:
                    mapping[str(i)] = col_clean
                elif col_clean in field_by_label:
                    mapping[str(i)] = field_by_label[col_clean].name
                else:
                    mapping[str(i)] = col_clean
            self.column_mapping_json = json.dumps(mapping)
        else:
            self.column_mapping_json = json.dumps({str(i): '' for i in range(len(rows[0]) if rows else 0)})

        self.state = 'mapping'
        return self._reopen()

    def action_run_validation(self):
        self.ensure_one()
        rows = self._parse_file()
        if not rows:
            raise UserError(_('No data to validate.'))

        mapping = json.loads(self.column_mapping_json or '{}')
        data_rows = rows[1:] if self.has_header else rows

        Rule = self.env['field.validation.rule']
        all_results = []

        for row_idx, row in enumerate(data_rows, start=2 if self.has_header else 1):
            row_dict = {}
            for col_idx, value in enumerate(row):
                field_name = mapping.get(str(col_idx), '')
                if field_name:
                    row_dict[field_name] = value if value != '' else None

            if self.ruleset_id:
                errors = self.ruleset_id.validate_row(row_dict)
            else:
                errors = Rule.validate_row(self.model_name, row_dict)

            all_results.append({
                'row': row_idx,
                'data': row_dict,
                'errors': errors,
            })

        total = len(all_results)
        err_rows = sum(1 for r in all_results if any(e['severity'] == 'error' for e in r['errors']))
        warn_rows = sum(1 for r in all_results if any(e['severity'] == 'warning' for e in r['errors']) and
                        not any(e['severity'] == 'error' for e in r['errors']))
        passed = total - err_rows - warn_rows

        log = self.env['field.validation.log'].create_log(
            model_name=self.model_name,
            results=all_results,
            source='wizard',
            ruleset=self.ruleset_id or None,
        )

        summary_html = self._build_summary_html(all_results, total, err_rows, warn_rows, passed)

        self.write({
            'state': 'result',
            'result_json': json.dumps(all_results, default=str),
            'log_id': log.id,
            'total_rows': total,
            'error_rows': err_rows,
            'warning_rows': warn_rows,
            'passed_rows': passed,
            'result_summary': summary_html,
        })
        return self._reopen()

    def action_back_to_upload(self):
        self.state = 'upload'
        return self._reopen()

    def action_back_to_mapping(self):
        self.state = 'mapping'
        return self._reopen()

    def action_view_log(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Validation Log'),
            'res_model': 'field.validation.log',
            'res_id': self.log_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def _parse_file(self):
        if not self.import_file:
            return []
        data = base64.b64decode(self.import_file)

        if self.file_type == 'csv':
            try:
                text = data.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = data.decode('latin-1')
            reader = csv.reader(io.StringIO(text), delimiter=self.csv_delimiter or ',')
            return list(reader)

        elif self.file_type == 'xlsx':
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
                ws = wb.active
                rows = []
                for row in ws.iter_rows(values_only=True):
                    rows.append([str(c) if c is not None else '' for c in row])
                return rows
            except ImportError:
                raise UserError(_(
                    'The openpyxl library is required for Excel file parsing. '
                    'Please install it: pip install openpyxl'
                ))
        return []

    def _build_summary_html(self, results, total, err_rows, warn_rows, passed):
        status_icon = '✅' if not err_rows else '❌'
        status_label = 'All rows passed!' if not err_rows else f'{err_rows} row(s) have errors'

        rows_html = ''
        for r in results:
            if not r['errors']:
                continue
            for e in r['errors']:
                sev_class = {'error': 'danger', 'warning': 'warning', 'info': 'info'}.get(e['severity'], 'secondary')
                rows_html += f"""
                <tr>
                    <td><strong>Row {r['row']}</strong></td>
                    <td>{e.get('field_label') or e.get('field', '')}</td>
                    <td><code>{e.get('value', '')}</code></td>
                    <td><span class="badge bg-{sev_class}">{e['severity'].upper()}</span></td>
                    <td>{e['message']}</td>
                </tr>
                """

        table_html = ''
        if rows_html:
            table_html = f"""
            <table class="table table-sm table-bordered mt-3" style="font-size:13px">
                <thead class="table-dark">
                    <tr>
                        <th>Row</th>
                        <th>Field</th>
                        <th>Value</th>
                        <th>Severity</th>
                        <th>Message</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            """

        return f"""
        <div class="fvm-result-summary p-3">
            <div class="d-flex gap-3 mb-3">
                <div class="card text-center px-4 py-2">
                    <div style="font-size:2em">{total}</div>
                    <small class="text-muted">Total Rows</small>
                </div>
                <div class="card text-center px-4 py-2 {'border-danger' if err_rows else 'border-success'}">
                    <div style="font-size:2em; color:{'#dc3545' if err_rows else '#198754'}">{err_rows}</div>
                    <small class="text-muted">Errors</small>
                </div>
                <div class="card text-center px-4 py-2 border-warning">
                    <div style="font-size:2em; color:#ffc107">{warn_rows}</div>
                    <small class="text-muted">Warnings</small>
                </div>
                <div class="card text-center px-4 py-2 border-success">
                    <div style="font-size:2em; color:#198754">{passed}</div>
                    <small class="text-muted">Passed</small>
                </div>
            </div>
            <div class="alert {'alert-danger' if err_rows else 'alert-success'}">
                {status_icon} <strong>{status_label}</strong>
            </div>
            {table_html}
        </div>
        """
