🛡

**Field Validation Rules Manager**

**Odoo v19 Custom Module**

*Technical Documentation & Developer Reference*

|              |                          |
|--------------|--------------------------|
| **Version**  | 19.0.1.0.0               |
| **Author**   | Mohamed Anwar            |
| **Category** | Technical / Import Tools |
| **Depends**  | base, web, base_setup    |

**1. Overview**

The **Field Validation Rules Manager** solves a critical pain point in Odoo data imports: validation errors that only surface after upload --- wasting time, corrupting data, and frustrating users. This module lets administrators define explicit validation rules for any field on any model, surface errors

**before** the import reaches the database, and generate Excel/CSV templates with embedded hints and dropdown validation.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>🎯 Problem</strong></p>
<p>Users experience cryptic errors during imports because field requirements are unclear, validation only fires after all data is loaded, and there is no way to test a file before committing it to the database.</p>
<p><strong>✅ Solution</strong></p>
<p>A configurable rules engine where admins define per-field validations, users pre-validate their files through a 3-step wizard, and generated templates carry hints, dropdowns, and a rules reference sheet directly inside the Excel file.</p></td>
</tr>
</tbody>
</table>

**2. Module Structure**

> field_validation_manager/
>
> ├── \_\_manifest\_\_.py \# Module metadata & asset declarations
>
> ├── \_\_init\_\_.py \# Package entry point
>
> │
>
> ├── models/
>
> │ ├── \_\_init\_\_.py
>
> │ ├── field_validation_rule.py \# Core rule model + validation engine
>
> │ ├── field_validation_ruleset.py \# Named rule bundles
>
> │ ├── field_validation_log.py \# Audit log + log line models
>
> │ └── field_validation_mixin.py \# AbstractModel mixin for any model
>
> │
>
> ├── wizard/
>
> │ ├── \_\_init\_\_.py
>
> │ ├── import_validator_wizard.py \# 3-step pre-import validator
>
> │ ├── import_validator_wizard_views.xml \# Wizard form view
>
> │ ├── template_generator_wizard.py \# Excel/CSV template builder
>
> │ └── template_generator_wizard_views.xml
>
> │
>
> ├── views/
>
> │ ├── field_validation_rule_views.xml \# Form, List, Kanban, Search
>
> │ ├── field_validation_ruleset_views.xml
>
> │ ├── field_validation_log_views.xml
>
> │ └── field_validation_menu.xml \# Full menu hierarchy
>
> │
>
> ├── controllers/
>
> │ ├── \_\_init\_\_.py
>
> │ └── main.py \# JSON-RPC API endpoints
>
> │
>
> ├── security/
>
> │ ├── field_validation_groups.xml \# User / Manager groups
>
> │ └── ir.model.access.csv \# ACL rules
>
> │
>
> ├── data/
>
> │ └── field_validation_data.xml \# Sequence + demo rules for res.partner
>
> │
>
> └── static/src/
>
> ├── css/field_validation.css \# Backend styles
>
> ├── js/field_validation_widget.js \# Live validation JS widget
>
> └── img/icon.svg \# App menu icon

**3. Models Reference**

**3.1 field.validation.rule**

The central model. Each record represents one validation constraint applied to one field on one model.

|                                 |             |                                                                   |
|---------------------------------|-------------|-------------------------------------------------------------------|
| **Field**                       | **Type**    | **Description**                                                   |
| name                            | *Char*      | Short descriptive name for the rule.                              |
| model_id                        | *Many2one*  | Target ir.model --- non-transient models only.                    |
| field_id                        | *Many2one*  | Target ir.model.fields --- excludes o2m/m2m/binary.               |
| rule_type                       | *Selection* | 15 rule types --- see Rule Types table below.                     |
| severity                        | *Selection* | error (blocks), warning (allows), info (suggests).                |
| sequence                        | *Integer*   | Evaluation order within the same field. Default 10.               |
| error_message                   | *Text*      | Supports placeholders: {field}, {value}, {min}, {max}, {allowed}. |
| hint_text                       | *Text*      | Short note embedded in generated import template columns.         |
| regex_pattern                   | *Char*      | Python re pattern. Used when rule_type = regex.                   |
| param_min / param_max           | *Float*     | Numeric bounds for length/value rules.                            |
| param_min_date / param_max_date | *Date*      | Date bounds for min_value / max_value rules.                      |
| allowed_values_raw              | *Text*      | One allowed value per line (allowed_values rule).                 |
| depends_on_field_id             | *Many2one*  | Trigger field for dependency rule.                                |
| depends_on_value                | *Char*      | The value depends_on_field must hold to activate.                 |
| python_code                     | *Text*      | Arbitrary Python returning True/False. See §3.1.1.                |
| date_format_str                 | *Char*      | strptime format string e.g. %d/%m/%Y.                             |
| run_count / fail_count          | *Integer*   | Statistics counters (auto-incremented).                           |
| ruleset_ids                     | *Many2many* | Rule sets this rule belongs to.                                   |

**3.1.1 Rule Types**

|                |                        |                                                                      |
|----------------|------------------------|----------------------------------------------------------------------|
| **Value**      | **Name**               | **Validates**                                                        |
| required       | **Required Field**     | Value is not None / empty string / False.                            |
| regex          | **Regex Pattern**      | Value matches Python regex_pattern (re.fullmatch).                   |
| min_length     | **Minimum Length**     | len(str(value)) \>= param_min.                                       |
| max_length     | **Maximum Length**     | len(str(value)) \<= param_max.                                       |
| min_value      | **Minimum Value**      | Numeric: float(value) \>= param_min. Date: value \>= param_min_date. |
| max_value      | **Maximum Value**      | Numeric: float(value) \<= param_max. Date: value \<= param_max_date. |
| allowed_values | **Allowed Values**     | str(value) in lines from allowed_values_raw.                         |
| unique         | **Unique Value**       | No other record on this model has this value.                        |
| dependency     | **Field Dependency**   | Field required when depends_on_field == depends_on_value.            |
| python         | **Custom Python**      | Executes python_code with value, record, env in scope.               |
| email          | **Valid Email**        | Matches standard email regex.                                        |
| url            | **Valid URL**          | Starts with http:// or https://.                                     |
| phone          | **Valid Phone**        | Matches international phone format (+XX, spaces, dashes).            |
| date_format    | **Date Format**        | Parses successfully with date_format_str (strptime).                 |
| not_future     | **Date Not in Future** | value \<= date.today().                                              |
| not_past       | **Date Not in Past**   | value \>= date.today().                                              |

**3.1.2 Core API Methods**

|                                            |                                                                                                                     |
|--------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| **Method**                                 | **Description**                                                                                                     |
| validate_value(value, record)              | Validates a single value. Returns (bool, str\|None). Increments run_count / fail_count automatically.               |
| get_rules_for_model(model_name)            | @api.model --- Returns a dict keyed by field_name with rule metadata. Used by the template generator and JS widget. |
| validate_row(model_name, row_dict, record) | @api.model --- Runs all active rules for the model against a full row dict. Returns list of error dicts.            |

**3.2 field.validation.ruleset**

A named collection of rules scoped to one model. Use rule sets when different import scenarios require different subsets of rules --- e.g. a \"Customer Import\" set vs a \"Vendor Import\" set, both on res.partner.

|                     |             |                                                           |
|---------------------|-------------|-----------------------------------------------------------|
| **Field**           | **Type**    | **Description**                                           |
| name                | *Char*      | Human-readable name for the rule set.                     |
| model_id            | *Many2one*  | Primary model --- filters available rules.                |
| rule_ids            | *Many2many* | Rules in this set (field.validation.rule).                |
| import_count        | *Integer*   | Times this set was used in a validation run.              |
| include_example_row | *Boolean*   | Whether to include an example row in generated templates. |
| template_notes      | *Text*      | Notes embedded in the generated template.                 |

**3.3 field.validation.log**

An immutable audit record created every time the Import Validator wizard runs. Contains header-level stats and a One2many of log lines (field.validation.log.line) with row-level detail.

|                                                      |                                                                               |
|------------------------------------------------------|-------------------------------------------------------------------------------|
| **Field**                                            | **Description**                                                               |
| log_ref                                              | Auto-generated sequence reference (FVL-00001, ...).                           |
| total_rows / error_rows / warning_rows / passed_rows | Aggregate row counts from the validation run.                                 |
| status                                               | passed \| warnings \| failed --- derived from error/warning counts.           |
| source                                               | wizard \| import \| api \| manual --- where the validation was triggered.     |
| detail_ids                                           | One2many to field.validation.log.line (row, field, value, severity, message). |

**3.4 field.validation.mixin**

An AbstractModel that any custom model can inherit to add automatic on-create / on-write validation. When \_fvm_enabled = True, every create() and write() call runs the active rules for that model and raises ValidationError on failures.

> \# Example usage in your custom model
>
> class SaleOrderCustom(models.Model):
>
> \_name = \"sale.order\"
>
> \_inherit = \[\"sale.order\", \"field.validation.mixin\"\]
>
> \_fvm_enabled = True
>
> \# Block writes on both errors and warnings:
>
> \_fvm_severity_threshold = \"warning\"

**4. Wizards**

**4.1 Import Pre-Validator Wizard**

A 3-step transient wizard that validates a CSV or Excel file before it is committed to the database.

**Step 1 --- Upload**

- Select the Target Model and (optionally) a Rule Set.

- Upload a CSV or Excel file.

- Set the delimiter (CSV) and whether a header row is present.

**Step 2 --- Map Columns**

- Columns are auto-detected from the header row.

- Column names are matched to field technical names first, then to field labels (case-insensitive).

- Unmapped columns are silently skipped during validation.

**Step 3 --- Results**

- An HTML summary table shows per-row, per-column errors and warnings.

- Stats cards display Total / Errors / Warnings / Passed counts.

- A Validation Log record is created automatically.

- The \"View Full Log\" button opens the detailed log form.

**4.2 Import Template Generator**

Generates an Excel (.xlsx) or CSV template pre-configured with validation hints for a chosen model.

**Excel Template Features**

- **Red column headers** --- Fields with a \"required\" rule have a red header; optional fields are blue.

- **Hint row (Row 2)** --- Each column shows the rule hints: \"Required \| Max: 128 \| Pattern: ...\"

- **Example row (Row 3)** --- Auto-generated sensible example values (can be turned off).

- **Dropdown validation** --- Excel Data Validation dropdowns auto-created for \"allowed_values\" rules (up to 255 chars).

- **Validation Rules sheet** --- A separate sheet listing every rule, severity, and error message for reference.

- **Legend box** --- Color key embedded top-right of the data sheet.

**5. JSON-RPC API Endpoints**

Two HTTP endpoints are available for external integrations or custom JavaScript widgets.

|                                             |                                                                                                                                   |
|---------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| **Endpoint**                                | **Description**                                                                                                                   |
| POST /field_validation/validate_row         | Validate a row dict against active rules. Body: { model_name, row_dict, ruleset_id? }. Returns { valid: bool, errors: \[\...\] }. |
| POST /field_validation/rules/\<model_name\> | Return all active rules for a model, structured for template generation and JS widgets. Returns a dict keyed by field_name.       |

> // Example: validate a row from JavaScript
>
> const result = await fetch(\"/field_validation/validate_row\", {
>
> method: \"POST\",
>
> headers: { \"Content-Type\": \"application/json\" },
>
> body: JSON.stringify({
>
> jsonrpc: \"2.0\", method: \"call\", id: 1,
>
> params: {
>
> model_name: \"res.partner\",
>
> row_dict: { name: \"\", email: \"not-an-email\" }
>
> }
>
> })
>
> });
>
> // Returns: { valid: false, errors: \[{ field: \"name\", severity: \"error\", message: \"\...\" }\] }

**6. Security**

|                              |                                |                                                                                       |
|------------------------------|--------------------------------|---------------------------------------------------------------------------------------|
| **Group**                    | **Technical ID**               | **Permissions**                                                                       |
| **Field Validation User**    | group_field_validation_user    | Read rules and rule sets. Run wizards (create transient records). View logs.          |
| **Field Validation Manager** | group_field_validation_manager | Full CRUD on rules, rule sets, and logs. Implied: User group. Auto-assigned to admin. |

**7. Menu Structure**

> Field Validation (top-level app, sequence 85)
>
> │
>
> ├── Configuration
>
> │ ├── Validation Rules → field.validation.rule (List / Form / Kanban)
>
> │ └── Rule Sets → field.validation.ruleset (List / Form)
>
> │
>
> ├── Import Tools
>
> │ ├── Pre-Import Validator → import.validator.wizard (dialog)
>
> │ └── Generate Import Template → template.generator.wizard (dialog)
>
> │
>
> └── Reports
>
> └── Validation Logs → field.validation.log (List / Form)

**8. Demo Data**

The following records are loaded on installation (noupdate=\"1\" --- safe to modify post-install):

|                                          |                       |                            |
|------------------------------------------|-----------------------|----------------------------|
| **Record**                               | **Model / Field**     | **Rule Type & Severity**   |
| **Partner Name -- Required**             | res.partner / name    | required --- error         |
| **Partner Email -- Valid Format**        | res.partner / email   | email --- error            |
| **Partner Phone -- Valid Format**        | res.partner / phone   | phone --- warning          |
| **Partner Website -- Valid URL**         | res.partner / website | url --- warning            |
| **Partner Name -- Max 128 Characters**   | res.partner / name    | max_length (128) --- error |
| **Partner Import -- Standard (ruleset)** | res.partner           | Bundles all 5 rules above  |

**9. Installation & Requirements**

**9.1 Requirements**

|                                       |                                                                                         |
|---------------------------------------|-----------------------------------------------------------------------------------------|
| **Requirement**                       | **Notes**                                                                               |
| **Odoo 19 (Community or Enterprise)** | Module is compatible with both editions.                                                |
| **Python ≥ 3.10**                     | Standard with Odoo 19.                                                                  |
| **openpyxl ≥ 3.1**                    | Required for Excel template generation and .xlsx parsing. Install: pip install openpyxl |
| **base, web, base_setup**             | Standard Odoo modules --- always present.                                               |

**9.2 Installation Steps**

1.  Copy the field_validation_manager/ directory into your Odoo addons path.

2.  Install openpyxl: pip install openpyxl \--break-system-packages

3.  Restart the Odoo server.

4.  In Settings → Apps, click **Update App List**.

5.  Search for **Field Validation Rules Manager** and click **Install**.

6.  Navigate to the **Field Validation** top-level menu to verify installation.

**10. Custom Python Rules --- Reference**

When rule_type = python, the python_code field is executed in a sandboxed local scope. The last expression or a return statement determines the result.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Available Variables</strong></p>
<blockquote>
<p>value: The raw field value being validated.</p>
<p>record: The Odoo recordset context (may be a NewId record for create).</p>
<p>env: The Odoo Environment (env["res.partner"].search(…) etc.)</p>
<p>model_name: String name of the model, e.g. 'res.partner'.</p>
<p>field_name: Technical field name, e.g. 'email'.</p>
<p>re: Python re module (pre-imported).</p>
<p>datetime / date: datetime and date classes (pre-imported).</p>
</blockquote></td>
</tr>
</tbody>
</table>

**Examples**

> \# Must be 18 or older
>
> if not value: return True
>
> return int(value) \>= 18
>
> \# VAT number must be unique among active partners
>
> if not value: return True
>
> count = env\[\"res.partner\"\].search_count(\[
>
> (\"vat\", \"=\", value), (\"active\", \"=\", True)
>
> \])
>
> return count == 0
>
> \# Postal code format for Egypt (5 digits)
>
> import re
>
> if not value: return True
>
> return bool(re.fullmatch(r\"\d{5}\", str(value)))

**11. Error Message Placeholders**

All error_message fields support Python .format() placeholders substituted at runtime:

|                 |                                                                           |
|-----------------|---------------------------------------------------------------------------|
| **Placeholder** | **Replaced With**                                                         |
| {field}         | The field\'s label (field_description), e.g. \"Email Address\".           |
| {value}         | The actual value that failed validation.                                  |
| {min}           | The param_min value (numeric minimum or minimum length).                  |
| {max}           | The param_max value (numeric maximum or maximum length).                  |
| {min_date}      | The param_min_date value.                                                 |
| {max_date}      | The param_max_date value.                                                 |
| {allowed}       | Comma-separated preview of allowed_values_raw (first 5 values + \"...\"). |

> \# Example error_message values:
>
> Field \"{field}\" value \"{value}\" is below the minimum of {min}.
>
> Field \"{field}\" is not in the allowed list: {allowed}.
>
> \"{value}\" is not a valid email address for field \"{field}\".

**12. Changelog**

|                |          |                                                                                                                                       |
|----------------|----------|---------------------------------------------------------------------------------------------------------------------------------------|
| **Version**    | **Date** | **Changes**                                                                                                                           |
| **19.0.1.0.0** | 2025     | Initial release. 15 rule types, 3-step import validator, Excel/CSV template generator, rule sets, audit log, JS widget, JSON-RPC API. |

|                                                                            |
|----------------------------------------------------------------------------|
| Field Validation Rules Manager · v19.0.1.0.0 · **Odoo v19 Custom Module**  |
