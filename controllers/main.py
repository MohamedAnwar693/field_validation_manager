# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request


class FieldValidationController(http.Controller):

    @http.route('/field_validation/validate_row', type='json', auth='user', methods=['POST'])
    def validate_row(self, model_name, row_dict, ruleset_id=None):
        """
        JSON API endpoint for real-time row validation.

        POST body:
            {
                "model_name": "res.partner",
                "row_dict": {"name": "John", "email": "bad-email"},
                "ruleset_id": 5  (optional)
            }
        Returns:
            {
                "valid": false,
                "errors": [{"field": ..., "severity": ..., "message": ...}]
            }
        """
        Rule = request.env['field.validation.rule']
        if ruleset_id:
            ruleset = request.env['field.validation.ruleset'].browse(ruleset_id)
            errors = ruleset.validate_row(row_dict)
        else:
            errors = Rule.validate_row(model_name, row_dict)
        return {
            'valid': not any(e['severity'] == 'error' for e in errors),
            'errors': errors,
        }

    @http.route('/field_validation/rules/<string:model_name>', type='json', auth='user', methods=['POST'])
    def get_rules(self, model_name):
        rules = request.env['field.validation.rule'].get_rules_for_model(model_name)
        return rules
