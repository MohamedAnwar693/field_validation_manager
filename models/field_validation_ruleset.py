from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FieldValidationRuleSet(models.Model):
    _name = 'field.validation.ruleset'
    _description = 'Field Validation Rule Set'
    _order = 'name'

    name = fields.Char(
        string='Rule Set Name',
        required=True,
        help='A named collection of validation rules for a specific import scenario.',
    )
    description = fields.Text(
        string='Description',
        help='What this rule set is for, when to use it, etc.',
    )
    active = fields.Boolean(string='Active', default=True)
    color = fields.Integer(string='Color Index')

    model_id = fields.Many2one(
        'ir.model',
        string='Primary Model',
        required=True,
        domain=[('transient', '=', False)],
        help='The model this rule set is designed for.',
    )
    model_name = fields.Char(related='model_id.model', store=True)

    rule_ids = fields.Many2many(
        'field.validation.rule',
        'ruleset_rule_rel',
        'ruleset_id',
        'rule_id',
        string='Validation Rules',
        domain="[('model_id', '=', model_id)]",
    )
    rule_count = fields.Integer(
        string='Rule Count',
        compute='_compute_rule_count',
        store=True,
    )

    import_count = fields.Integer(
        string='Times Used for Import',
        default=0,
        readonly=True,
    )
    last_used = fields.Datetime(
        string='Last Used',
        readonly=True,
    )

    include_example_row = fields.Boolean(
        string='Include Example Row in Template',
        default=True,
    )
    template_notes = fields.Text(
        string='Template Notes',
        help='General notes to include in the generated import template.',
    )

    @api.depends('rule_ids')
    def _compute_rule_count(self):
        for rec in self:
            rec.rule_count = len(rec.rule_ids)

    def validate_row(self, row_dict, record=None):
        self.ensure_one()
        errors = []
        for rule in self.rule_ids.filtered('active').sorted('sequence'):
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
        self.sudo().write({
            'import_count': self.import_count + 1,
            'last_used': fields.Datetime.now(),
        })
        return errors

    def action_open_rules(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rules in %s') % self.name,
            'res_model': 'field.validation.rule',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.rule_ids.ids)],
            'context': {'default_model_id': self.model_id.id},
        }
