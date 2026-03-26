from odoo import models, api, _
from odoo.exceptions import ValidationError


class FieldValidationMixin(models.AbstractModel):
    _name = 'field.validation.mixin'
    _description = 'Field Validation Mixin'

    _fvm_enabled = False
    _fvm_severity_threshold = 'error'

    @api.model_create_multi
    def create(self, vals_list):
        if self._fvm_enabled:
            for vals in vals_list:
                self._fvm_run(vals)
        return super().create(vals_list)

    def write(self, vals):
        if self._fvm_enabled:
            self._fvm_run(vals)
        return super().write(vals)

    def _fvm_run(self, vals):
        Rule = self.env['field.validation.rule']
        errors = Rule.validate_row(self._name, vals)
        blocking = [
            e for e in errors
            if e['severity'] == 'error'
            or (self._fvm_severity_threshold == 'warning' and e['severity'] == 'warning')
        ]
        if blocking:
            msg_lines = [_('Validation errors found:')]
            for e in blocking:
                prefix = '❌' if e['severity'] == 'error' else '⚠️'
                msg_lines.append(f"  {prefix} [{e['field_label']}] {e['message']}")
            raise ValidationError('\n'.join(msg_lines))
