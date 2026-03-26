import re
import ast
from datetime import date, datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


RULE_TYPE_SELECTION = [
    ('required',        'Required Field'),
    ('regex',           'Regex Pattern'),
    ('min_length',      'Minimum Length'),
    ('max_length',      'Maximum Length'),
    ('min_value',       'Minimum Value (Numeric/Date)'),
    ('max_value',       'Maximum Value (Numeric/Date)'),
    ('allowed_values',  'Allowed Values'),
    ('unique',          'Unique Value'),
    ('dependency',      'Field Dependency'),
    ('python',          'Custom Python Expression'),
    ('email',           'Valid Email'),
    ('url',             'Valid URL'),
    ('phone',           'Valid Phone Number'),
    ('date_format',     'Date Format'),
    ('not_future',      'Date Not in Future'),
    ('not_past',        'Date Not in Past'),
]

SEVERITY_SELECTION = [
    ('error',   'Error (Block Import)'),
    ('warning', 'Warning (Allow with Notice)'),
    ('info',    'Info (Suggest Only)'),
]


class FieldValidationRule(models.Model):
    _name = 'field.validation.rule'
    _description = 'Field Validation Rule'
    _order = 'model_id, field_id, sequence'
    _rec_name = 'display_name_computed'

    name = fields.Char(
        string='Rule Name',
        required=True,
        help='Short descriptive name for this validation rule.',
    )
    display_name_computed = fields.Char(
        string='Display Name',
        compute='_compute_display_name_computed',
        store=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Evaluation order within the same field.',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    color = fields.Integer(string='Color Index')

    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain=[('transient', '=', False)],
        help='The Odoo model this rule applies to.',
    )
    model_name = fields.Char(
        related='model_id.model',
        store=True,
        string='Model Technical Name',
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', model_id), ('ttype', 'not in', ['one2many', 'many2many'])]",
        help='The field this rule validates.',
    )
    field_name = fields.Char(
        related='field_id.name',
        store=True,
        string='Field Technical Name',
    )
    field_ttype = fields.Selection(
        related='field_id.ttype',
        string='Field Type',
        store=True,
    )
    field_label = fields.Char(
        related='field_id.field_description',
        string='Field Label',
    )

    rule_type = fields.Selection(
        RULE_TYPE_SELECTION,
        string='Rule Type',
        required=True,
        default='required',
    )
    severity = fields.Selection(
        SEVERITY_SELECTION,
        string='Severity',
        required=True,
        default='error',
    )

    regex_pattern = fields.Char(
        string='Regex Pattern',
        help='Python-compatible regular expression. Example: ^[A-Z]{2,5}$',
    )
    regex_flags = fields.Char(
        string='Regex Flags',
        default='',
        help='Optional flags: I (ignore case), M (multiline), S (dotall). Comma-separated.',
    )

    param_min = fields.Float(
        string='Minimum',
        digits=(16, 4),
        help='Minimum length (for string rules) or minimum numeric/date value.',
    )
    param_max = fields.Float(
        string='Maximum',
        digits=(16, 4),
        help='Maximum length (for string rules) or maximum numeric/date value.',
    )
    param_min_date = fields.Date(string='Minimum Date')
    param_max_date = fields.Date(string='Maximum Date')

    allowed_values_raw = fields.Text(
        string='Allowed Values',
        help='One value per line. Used for "Allowed Values" rule type.',
    )
    allowed_values_list = fields.Char(
        string='Allowed Values (Preview)',
        compute='_compute_allowed_values_list',
    )

    depends_on_field_id = fields.Many2one(
        'ir.model.fields',
        string='Depends On Field',
        domain="[('model_id', '=', model_id)]",
        help='This field is required only when the "Depends On" field has a specific value.',
    )
    depends_on_value = fields.Char(
        string='Depends On Value',
        help='The value the "Depends On" field must have to trigger this rule.',
    )

    date_format_str = fields.Char(
        string='Expected Date Format',
        default='%Y-%m-%d',
        help='Python strptime format string. Example: %d/%m/%Y',
    )

    python_code = fields.Text(
        string='Python Code',
        help="""Write a Python expression that returns True (valid) or False (invalid).
Available variables:
  - value       : the field value being validated
  - record      : the record being validated (may be a new record)
  - env         : Odoo environment
  - model_name  : string name of the model
  - field_name  : string name of the field

Example (must be adult):
  if not value: return True
  return int(value) >= 18
""",
    )

    error_message = fields.Text(
        string='Error Message',
        required=True,
        default='Validation failed for field "{field}".',
        help="""Custom error message shown when this rule fails.
Placeholders:
  {field}   – replaced with the field label
  {value}   – replaced with the actual value
  {min}     – replaced with param_min
  {max}     – replaced with param_max
  {allowed} – replaced with allowed values list
""",
    )
    hint_text = fields.Text(
        string='Import Hint / Template Note',
        help='Brief instruction shown in the generated import template column header.',
    )

    ruleset_ids = fields.Many2many(
        'field.validation.ruleset',
        'ruleset_rule_rel',
        'rule_id',
        'ruleset_id',
        string='Rule Sets',
    )

    run_count = fields.Integer(
        string='Times Triggered',
        default=0,
        readonly=True,
    )
    fail_count = fields.Integer(
        string='Times Failed',
        default=0,
        readonly=True,
    )
    last_triggered = fields.Datetime(
        string='Last Triggered',
        readonly=True,
    )

    @api.depends('name', 'model_id', 'field_id', 'rule_type')
    def _compute_display_name_computed(self):
        for rec in self:
            model_label = rec.model_id.name or ''
            field_label = rec.field_id.field_description or ''
            rec.display_name_computed = f'[{model_label}] {field_label} – {rec.name}'

    @api.depends('allowed_values_raw')
    def _compute_allowed_values_list(self):
        for rec in self:
            if rec.allowed_values_raw:
                vals = [v.strip() for v in rec.allowed_values_raw.splitlines() if v.strip()]
                rec.allowed_values_list = ', '.join(vals[:5]) + ('…' if len(vals) > 5 else '')
            else:
                rec.allowed_values_list = ''

    @api.constrains('regex_pattern')
    def _check_regex_pattern(self):
        for rec in self:
            if rec.rule_type == 'regex' and rec.regex_pattern:
                try:
                    re.compile(rec.regex_pattern)
                except re.error as e:
                    raise ValidationError(_('Invalid regex pattern: %s') % str(e))

    @api.constrains('python_code')
    def _check_python_code(self):
        for rec in self:
            if rec.rule_type == 'python' and rec.python_code:
                try:
                    ast.parse(rec.python_code)
                except SyntaxError as e:
                    raise ValidationError(_('Syntax error in Python code: %s') % str(e))

    @api.constrains('param_min', 'param_max')
    def _check_min_max(self):
        for rec in self:
            if rec.rule_type in ('min_length', 'max_length') or (
                rec.rule_type == 'min_value' and rec.rule_type == 'max_value'
            ):
                if rec.param_min and rec.param_max and rec.param_min > rec.param_max:
                    raise ValidationError(_('Minimum value cannot exceed Maximum value.'))

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.field_id = False
        self.depends_on_field_id = False

    @api.onchange('rule_type')
    def _onchange_rule_type(self):
        defaults = {
            'required':       'Field "{field}" is required and cannot be empty.',
            'regex':          'Field "{field}" value "{value}" does not match the required pattern.',
            'min_length':     'Field "{field}" must be at least {min} characters long.',
            'max_length':     'Field "{field}" must not exceed {max} characters.',
            'min_value':      'Field "{field}" value "{value}" is below the minimum of {min}.',
            'max_value':      'Field "{field}" value "{value}" exceeds the maximum of {max}.',
            'allowed_values': 'Field "{field}" value "{value}" is not in the allowed list: {allowed}.',
            'unique':         'Field "{field}" value "{value}" must be unique — a duplicate was found.',
            'dependency':     'Field "{field}" is required when the related field has value "{value}".',
            'python':         'Field "{field}" failed the custom validation check.',
            'email':          'Field "{field}" value "{value}" is not a valid email address.',
            'url':            'Field "{field}" value "{value}" is not a valid URL.',
            'phone':          'Field "{field}" value "{value}" is not a valid phone number.',
            'date_format':    'Field "{field}" value "{value}" does not match the expected date format.',
            'not_future':     'Field "{field}" date "{value}" cannot be in the future.',
            'not_past':       'Field "{field}" date "{value}" cannot be in the past.',
        }
        if self.rule_type and not self.error_message or self.error_message == self._fields['error_message'].default:
            self.error_message = defaults.get(self.rule_type, 'Validation failed for field "{field}".')

    def validate_value(self, value, record=None):
        self.ensure_one()

        self.sudo().write({
            'run_count': self.run_count + 1,
            'last_triggered': fields.Datetime.now(),
        })

        is_valid, error = self._dispatch_rule(value, record)

        if not is_valid:
            self.sudo().write({'fail_count': self.fail_count + 1})
            msg = self._format_error(value)
            return False, msg

        return True, None

    def _dispatch_rule(self, value, record):
        rt = self.rule_type
        if rt == 'required':        return self._validate_required(value)
        if rt == 'regex':           return self._validate_regex(value)
        if rt == 'min_length':      return self._validate_min_length(value)
        if rt == 'max_length':      return self._validate_max_length(value)
        if rt == 'min_value':       return self._validate_min_value(value)
        if rt == 'max_value':       return self._validate_max_value(value)
        if rt == 'allowed_values':  return self._validate_allowed_values(value)
        if rt == 'unique':          return self._validate_unique(value, record)
        if rt == 'dependency':      return self._validate_dependency(value, record)
        if rt == 'python':          return self._validate_python(value, record)
        if rt == 'email':           return self._validate_email(value)
        if rt == 'url':             return self._validate_url(value)
        if rt == 'phone':           return self._validate_phone(value)
        if rt == 'date_format':     return self._validate_date_format(value)
        if rt == 'not_future':      return self._validate_not_future(value)
        if rt == 'not_past':        return self._validate_not_past(value)
        return True, None

    def _validate_required(self, value):
        if value is None or value == '' or value is False:
            return False, 'required'
        return True, None

    def _validate_regex(self, value):
        if not value:
            return True, None
        if not self.regex_pattern:
            return True, None
        flags = 0
        if self.regex_flags:
            for f in self.regex_flags.upper().split(','):
                f = f.strip()
                if f == 'I': flags |= re.IGNORECASE
                elif f == 'M': flags |= re.MULTILINE
                elif f == 'S': flags |= re.DOTALL
        if re.fullmatch(self.regex_pattern, str(value), flags):
            return True, None
        return False, 'regex'

    def _validate_min_length(self, value):
        if not value:
            return True, None
        if len(str(value)) < int(self.param_min):
            return False, 'min_length'
        return True, None

    def _validate_max_length(self, value):
        if not value:
            return True, None
        if len(str(value)) > int(self.param_max):
            return False, 'max_length'
        return True, None

    def _validate_min_value(self, value):
        if value is None or value == '':
            return True, None
        try:
            if self.param_min_date:
                val_date = fields.Date.from_string(str(value)) if isinstance(value, str) else value
                if val_date < self.param_min_date:
                    return False, 'min_value'
            else:
                if float(value) < self.param_min:
                    return False, 'min_value'
        except (ValueError, TypeError):
            return False, 'min_value'
        return True, None

    def _validate_max_value(self, value):
        if value is None or value == '':
            return True, None
        try:
            if self.param_max_date:
                val_date = fields.Date.from_string(str(value)) if isinstance(value, str) else value
                if val_date > self.param_max_date:
                    return False, 'max_value'
            else:
                if float(value) > self.param_max:
                    return False, 'max_value'
        except (ValueError, TypeError):
            return False, 'max_value'
        return True, None

    def _validate_allowed_values(self, value):
        if not value:
            return True, None
        if not self.allowed_values_raw:
            return True, None
        allowed = [v.strip() for v in self.allowed_values_raw.splitlines() if v.strip()]
        if str(value).strip() not in allowed:
            return False, 'allowed_values'
        return True, None

    def _validate_unique(self, value, record):
        if not value or not self.model_name or not self.field_name:
            return True, None
        domain = [(self.field_name, '=', value)]
        if record and record.id:
            domain.append(('id', '!=', record.id))
        try:
            count = self.env[self.model_name].search_count(domain)
            if count > 0:
                return False, 'unique'
        except Exception:
            return True, None
        return True, None

    def _validate_dependency(self, value, record):
        if not self.depends_on_field_id or not record:
            return True, None
        dep_val = getattr(record, self.depends_on_field_id.name, None)
        if str(dep_val) == str(self.depends_on_value):
            if not value:
                return False, 'dependency'
        return True, None

    def _validate_python(self, value, record):
        if not self.python_code:
            return True, None
        local_ctx = {
            'value': value,
            'record': record,
            'env': self.env,
            'model_name': self.model_name,
            'field_name': self.field_name,
            'True': True,
            'False': False,
            'None': None,
            're': re,
            'datetime': datetime,
            'date': date,
        }
        try:
            code_lines = self.python_code.strip().splitlines()
            if code_lines:
                wrapped = '\n'.join(['def _fvm_check():'] + ['    ' + l for l in code_lines])
                exec(wrapped, local_ctx)
                result = local_ctx['_fvm_check']()
                if result is False:
                    return False, 'python'
        except Exception as e:
            return False, f'python_error: {e}'
        return True, None

    def _validate_email(self, value):
        if not value:
            return True, None
        pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, str(value)):
            return True, None
        return False, 'email'

    def _validate_url(self, value):
        if not value:
            return True, None
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if re.match(pattern, str(value)):
            return True, None
        return False, 'url'

    def _validate_phone(self, value):
        if not value:
            return True, None
        pattern = r'^\+?[\d\s\-\(\)\.]{7,20}$'
        if re.match(pattern, str(value)):
            return True, None
        return False, 'phone'

    def _validate_date_format(self, value):
        if not value:
            return True, None
        fmt = self.date_format_str or '%Y-%m-%d'
        try:
            datetime.strptime(str(value), fmt)
            return True, None
        except ValueError:
            return False, 'date_format'

    def _validate_not_future(self, value):
        if not value:
            return True, None
        try:
            if isinstance(value, (date, datetime)):
                val_date = value if isinstance(value, date) else value.date()
            else:
                val_date = fields.Date.from_string(str(value))
            if val_date > date.today():
                return False, 'not_future'
        except Exception:
            return False, 'not_future'
        return True, None

    def _validate_not_past(self, value):
        if not value:
            return True, None
        try:
            if isinstance(value, (date, datetime)):
                val_date = value if isinstance(value, date) else value.date()
            else:
                val_date = fields.Date.from_string(str(value))
            if val_date < date.today():
                return False, 'not_past'
        except Exception:
            return False, 'not_past'
        return True, None

    def _format_error(self, value):
        allowed = self.allowed_values_list or ''
        return (self.error_message or 'Validation failed.').format(
            field=self.field_id.field_description or self.field_name or '?',
            value=value,
            min=self.param_min,
            max=self.param_max,
            min_date=self.param_min_date or '',
            max_date=self.param_max_date or '',
            allowed=allowed,
        )

    @api.model
    def validate_row(self, model_name, row_dict, record=None):
        errors = []
        rules = self.search([
            ('model_name', '=', model_name),
            ('active', '=', True),
        ], order='sequence')

        for rule in rules:
            if rule.field_name not in row_dict:
                continue
            value = row_dict[rule.field_name]
            is_valid, msg = rule.validate_value(value, record)
            if not is_valid:
                errors.append({
                    'field': rule.field_name,
                    'field_label': rule.field_id.field_description,
                    'value': value,
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'severity': rule.severity,
                    'message': msg,
                })
        return errors

    @api.model
    def get_rules_for_model(self, model_name):
        rules = self.search([
            ('model_name', '=', model_name),
            ('active', '=', True),
        ], order='field_id, sequence')
        result = {}
        for rule in rules:
            fn = rule.field_name
            if fn not in result:
                result[fn] = {
                    'field_label': rule.field_label or fn,
                    'field_ttype': rule.field_ttype,
                    'rules': [],
                }
            result[fn]['rules'].append({
                'rule_id': rule.id,
                'rule_type': rule.rule_type,
                'severity': rule.severity,
                'error_message': rule.error_message,
                'hint_text': rule.hint_text or '',
                'required': rule.rule_type == 'required',
                'allowed_values': [
                    v.strip()
                    for v in (rule.allowed_values_raw or '').splitlines()
                    if v.strip()
                ] if rule.rule_type == 'allowed_values' else [],
                'regex_pattern': rule.regex_pattern or '',
                'param_min': rule.param_min,
                'param_max': rule.param_max,
                'date_format': rule.date_format_str or '',
            })
        return result
