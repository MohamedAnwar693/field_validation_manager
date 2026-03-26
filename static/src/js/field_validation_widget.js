/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onMounted } from "@odoo/owl";


async function validateFieldValue(rpc, modelName, fieldName, value, rulesetId = null) {
    try {
        const result = await rpc("/field_validation/validate_row", {
            model_name: modelName,
            row_dict: { [fieldName]: value },
            ruleset_id: rulesetId,
        });
        return result;
    } catch (e) {
        console.warn("[FVM] Validation endpoint error:", e);
        return { valid: true, errors: [] };
    }
}

function buildBadge(severity, message) {
    const colors = { error: "#dc3545", warning: "#ffc107", info: "#0dcaf0" };
    const textColors = { error: "#fff", warning: "#000", info: "#000" };
    const icons = { error: "✖", warning: "⚠", info: "ℹ" };
    const color = colors[severity] || "#6c757d";
    const text = textColors[severity] || "#fff";
    const icon = icons[severity] || "?";

    const el = document.createElement("div");
    el.className = "fvm-inline-badge";
    el.style.cssText = `
        display:inline-flex;align-items:center;gap:4px;
        margin-top:3px;padding:2px 8px;border-radius:4px;
        font-size:11px;font-weight:500;
        background:${color};color:${text};
        animation:fvm-fadein 0.2s ease;
    `;
    el.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    return el;
}

class FvmInlineValidatorWidget extends Component {
    static template = "field_validation_manager.InlineValidator";
    static props = {
        field_name: { type: String },
        model_name: { type: String },
        value: { type: [String, Number, Boolean], optional: true },
    };

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({ loading: false, errors: [] });

        onMounted(async () => {
            if (this.props.value !== undefined && this.props.value !== "") {
                await this.runValidation(this.props.value);
            }
        });
    }

    async runValidation(value) {
        this.state.loading = true;
        const result = await validateFieldValue(
            this.rpc,
            this.props.model_name,
            this.props.field_name,
            value
        );
        this.state.errors = result.errors || [];
        this.state.loading = false;
    }
}

registry.category("view_widgets").add("fvm_inline_validator", {
    component: FvmInlineValidatorWidget,
});

function attachLiveValidation(formEl, modelName, rpc) {
    if (!formEl || !modelName) return;

    const inputs = formEl.querySelectorAll(
        ".o_field_widget input, .o_field_widget textarea, .o_field_widget select"
    );

    inputs.forEach((input) => {
        const fieldWidget = input.closest(".o_field_widget");
        if (!fieldWidget) return;
        const fieldName = fieldWidget.getAttribute("name");
        if (!fieldName) return;

        input.addEventListener("blur", async () => {
            const value = input.value;
            if (!value) return;

            const oldBadge = fieldWidget.querySelector(".fvm-inline-badge");
            if (oldBadge) oldBadge.remove();

            const result = await validateFieldValue(rpc, modelName, fieldName, value);
            if (!result.valid && result.errors.length > 0) {
                const err = result.errors[0];
                const badge = buildBadge(err.severity, err.message);
                fieldWidget.appendChild(badge);
            }
        });
    });
}

const styleEl = document.createElement("style");
styleEl.textContent = `
    @keyframes fvm-fadein {
        from { opacity:0; transform:translateY(-4px); }
        to   { opacity:1; transform:translateY(0); }
    }
`;
document.head.appendChild(styleEl);

export { validateFieldValue, attachLiveValidation, buildBadge };
