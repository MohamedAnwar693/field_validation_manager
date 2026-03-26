from odoo import models, fields, api


class FieldValidationLog(models.Model):
    _name = 'field.validation.log'
    _description = 'Field Validation Log'
    _order = 'create_date desc'
    _rec_name = 'log_ref'

    log_ref = fields.Char(
        string='Log Reference',
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('field.validation.log') or 'FVL-NEW',
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        readonly=True,
    )
    model_name = fields.Char(string='Model', readonly=True)
    ruleset_id = fields.Many2one(
        'field.validation.ruleset',
        string='Rule Set Used',
        readonly=True,
    )
    source = fields.Selection([
        ('wizard',  'Import Validator Wizard'),
        ('import',  'Standard Import Hook'),
        ('api',     'Programmatic API'),
        ('manual',  'Manual Validation'),
    ], string='Triggered From', default='wizard', readonly=True)

    total_rows = fields.Integer(string='Total Rows Checked', readonly=True)
    error_rows = fields.Integer(string='Rows with Errors', readonly=True)
    warning_rows = fields.Integer(string='Rows with Warnings', readonly=True)
    passed_rows = fields.Integer(string='Rows Passed', readonly=True)

    status = fields.Selection([
        ('passed',   'All Passed'),
        ('warnings', 'Passed with Warnings'),
        ('failed',   'Errors Found'),
    ], string='Overall Status', readonly=True, default='passed')

    detail_ids = fields.One2many(
        'field.validation.log.line',
        'log_id',
        string='Error Details',
        readonly=True,
    )
    detail_count = fields.Integer(
        string='Detail Count',
        compute='_compute_detail_count',
    )

    notes = fields.Text(string='Notes')

    @api.depends('detail_ids')
    def _compute_detail_count(self):
        for rec in self:
            rec.detail_count = len(rec.detail_ids)

    def action_view_details(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Validation Details',
            'res_model': 'field.validation.log.line',
            'view_mode': 'list',
            'domain': [('log_id', '=', self.id)],
        }

    @api.model
    def create_log(self, model_name, results, source='wizard', ruleset=None):
        total = len(results)
        error_rows = sum(1 for r in results if any(e['severity'] == 'error' for e in r.get('errors', [])))
        warning_rows = sum(1 for r in results if any(e['severity'] == 'warning' for e in r.get('errors', [])))
        passed = total - error_rows

        if error_rows:
            status = 'failed'
        elif warning_rows:
            status = 'warnings'
        else:
            status = 'passed'

        log = self.create({
            'model_name': model_name,
            'ruleset_id': ruleset.id if ruleset else False,
            'source': source,
            'total_rows': total,
            'error_rows': error_rows,
            'warning_rows': warning_rows,
            'passed_rows': passed,
            'status': status,
        })

        lines = []
        for row_result in results:
            row_num = row_result.get('row', 0)
            for err in row_result.get('errors', []):
                lines.append({
                    'log_id': log.id,
                    'row_number': row_num,
                    'field_name': err.get('field', ''),
                    'field_label': err.get('field_label', ''),
                    'value': str(err.get('value', '')),
                    'rule_id': err.get('rule_id', False),
                    'severity': err.get('severity', 'error'),
                    'message': err.get('message', ''),
                })
        if lines:
            self.env['field.validation.log.line'].create(lines)

        return log


class FieldValidationLogLine(models.Model):
    _name = 'field.validation.log.line'
    _description = 'Field Validation Log Line'
    _order = 'log_id, row_number, field_name'

    log_id = fields.Many2one(
        'field.validation.log',
        string='Log',
        required=True,
        ondelete='cascade',
    )
    row_number = fields.Integer(string='Row #')
    field_name = fields.Char(string='Field (Technical)')
    field_label = fields.Char(string='Field Label')
    value = fields.Char(string='Value')
    rule_id = fields.Many2one('field.validation.rule', string='Rule', ondelete='set null')
    severity = fields.Selection([
        ('error',   'Error'),
        ('warning', 'Warning'),
        ('info',    'Info'),
    ], string='Severity', default='error')
    message = fields.Text(string='Message')
