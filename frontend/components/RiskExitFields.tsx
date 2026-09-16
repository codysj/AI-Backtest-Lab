"use client";

import type { RiskExitSettings } from "../lib/types";
import type { FormErrors } from "../lib/validation";

const fields: { key: keyof RiskExitSettings; label: string }[] = [
  { key: "stop_loss_pct", label: "Stop loss %" },
  { key: "take_profit_pct", label: "Take profit %" },
  { key: "trailing_stop_pct", label: "Trailing stop %" }
];

type RiskExitFieldsProps = {
  value: RiskExitSettings;
  errors: FormErrors;
  onChange: (value: RiskExitSettings) => void;
};

/** Optional protective exits. Inputs are percents; the API receives fractions. */
export function RiskExitFields({ value, errors, onChange }: RiskExitFieldsProps) {
  return (
    <div className="rounded-xl border border-lab-border bg-lab-surface p-4">
      <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-lab-secondary">Risk Exits</h3>
      <p className="mt-1 text-xs leading-5 text-lab-muted">
        Optional. Checked at each close and filled with the chosen execution timing. Leave blank to disable.
      </p>
      <div className="mt-3 grid grid-cols-3 gap-3">
        {fields.map((field) => {
          const fraction = value[field.key];
          return (
            <label key={field.key} className="block">
              <span className="text-xs font-medium text-lab-text">{field.label}</span>
              <input
                type="number"
                min={0.1}
                max={99}
                step={0.5}
                placeholder="off"
                value={fraction == null ? "" : Number((fraction * 100).toFixed(4))}
                onChange={(event) =>
                  onChange({
                    ...value,
                    [field.key]: event.target.value === "" ? null : Number(event.target.value) / 100
                  })
                }
                className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
              />
              {errors[field.key] ? <p className="mt-1 text-xs text-lab-red">{errors[field.key]}</p> : null}
            </label>
          );
        })}
      </div>
    </div>
  );
}
