{
    'name': 'Field Validation Rules Manager',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Define custom validation rules for any field, provide clear import error messages, and generate import templates with validation hints.',
    'description': """
        Field Validation Rules Manager
        ================================
        
        This module empowers administrators to:
        
        * Define custom validation rules for any field on any model
        * Attach meaningful error messages shown before and during imports
        * Generate Excel/CSV import templates with validation hints embedded
        * Run pre-import validation checks with a detailed report
        * Manage rule sets (groups of rules) for different import scenarios
        * View a validation dashboard with rule coverage and recent import stats

        Key Features:
        -------------
        - Rule types: Required, Regex Pattern, Min/Max Length, Numeric Range,
          Allowed Values (Selection), Unique, Date Range, Dependency, Custom Python
        - Per-rule custom error messages (supports {field} and {value} placeholders)
        - Import Template Generator: exports .xlsx with column headers, data-validation
          dropdowns, colored required-field headers, and an embedded "Rules" sheet
        - Pre-Import Validator wizard: paste/upload a CSV/Excel, get a per-row
          per-column validation report before committing any record
        - Rule Sets: bundle rules into named sets for reuse across import scenarios
        - Audit log of all validation events
        - Fully integrated with Odoo's standard import wizard via a hook
    """,
    'author': 'Mohamed Anwar',
    'depends': [
        'base',
        'web',
        'base_setup',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/field_validation_groups.xml',
        'data/field_validation_data.xml',
        'views/field_validation_rule_views.xml',
        'views/field_validation_ruleset_views.xml',
        'views/field_validation_log_views.xml',
        'views/field_validation_menu.xml',
        'wizard/import_validator_wizard_views.xml',
        'wizard/template_generator_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'field_validation_manager/static/src/css/field_validation.css',
            'field_validation_manager/static/src/js/field_validation_widget.js',
        ],
    },
    'images': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
