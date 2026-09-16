"use client";

import { CheckCircle2, ClipboardList, HelpCircle } from "lucide-react";
import { conditionLabel } from "../../lib/rules";
import type { ConditionSpec, StrategyCompileResponse, StrategyDraft } from "../../lib/types";
import { formatCurrency, formatDecimal, formatNumber } from "../formatters";
import { StrategyAssumptions } from "./StrategyAssumptions";
import { StrategyUnsupportedState } from "./StrategyUnsupportedState";

type StrategyDraftPreviewProps = {
  draft: StrategyDraft;
  responseWarnings: string[];
  responseUnsupported: string[];
  responseValidationErrors: string[];
  compileResponse: StrategyCompileResponse | null;
  isCompiling: boolean;
  compileError: string | null;
  loadMessage: string | null;
  onCompileAndLoad: () => void;
};

function labelize(value: string | null | undefined): string {
  if (!value) return "Not specified";
  return value.replaceAll("_", " ");
}

function jsonLabel(values: Record<string, number> | null | undefined): string {
  if (!values || Object.keys(values).length === 0) return "Not specified";
  return Object.entries(values)
    .map(([key, value]) => `${key.replaceAll("_", " ")} ${formatNumber(value)}`)
    .join(" / ");
}

function gridLabel(values: Record<string, number[]> | null | undefined): string {
  if (!values || Object.keys(values).length === 0) return "Not specified";
  return Object.entries(values)
    .map(([key, items]) => `${key.replaceAll("_", " ")} [${items.join(", ")}]`)
    .join(" / ");
}

function ruleListLabel(conditions: ConditionSpec[] | undefined, joiner: string): string {
  if (!conditions || conditions.length === 0) return "Not specified";
  return conditions.map(conditionLabel).join(` ${joiner} `);
}

function statusTone(status: StrategyDraft["status"]): string {
  if (status === "ready") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-100";
  if (status === "unsupported") return "border-lab-red/40 bg-lab-red/10 text-red-100";
  return "border-amber-500/30 bg-amber-500/10 text-amber-100";
}

function modeLabel(mode: StrategyDraft["target_mode"]): string {
  if (mode === "single_run") return "Single Run";
  if (mode === "grid_search") return "Grid Search";
  if (mode === "walk_forward") return "Walk-Forward";
  return "Unspecified";
}

function strategyInterpretation(draft: StrategyDraft): { entry: string; exit: string } {
  if (draft.strategy_kind === "momentum") {
    return {
      entry: "Fast SMA crosses above slow SMA.",
      exit: "Fast SMA crosses below slow SMA."
    };
  }
  if (draft.strategy_kind === "mean_reversion") {
    return {
      entry: "Close reaches or falls below the lower rolling band.",
      exit: "Close reaches or rises above the upper rolling band."
    };
  }
  if (draft.strategy_kind === "rsi_reversion") {
    return { entry: "RSI crosses down into the oversold level.", exit: "RSI reaches the overbought level." };
  }
  if (draft.strategy_kind === "donchian_breakout") {
    return { entry: "Close breaks above the prior entry-window high.", exit: "Close breaks below the prior exit-window low." };
  }
  if (draft.strategy_kind === "macd_crossover") {
    return { entry: "MACD line crosses above its signal line.", exit: "MACD line crosses below its signal line." };
  }
  if (draft.strategy_kind === "rule_based") {
    return {
      entry: ruleListLabel(draft.rule_spec?.rules.entry, "AND"),
      exit: ruleListLabel(draft.rule_spec?.rules.exit, "OR")
    };
  }
  return { entry: "Not available.", exit: "Not available." };
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-lab-border bg-lab-bg p-3">
      <div className="text-xs uppercase tracking-[0.16em] text-lab-muted">{label}</div>
      <div className="mt-1 break-words font-mono-finance text-sm text-lab-text">{value}</div>
    </div>
  );
}

export function StrategyDraftPreview({
  draft,
  responseWarnings,
  responseUnsupported,
  responseValidationErrors,
  compileResponse,
  isCompiling,
  compileError,
  loadMessage,
  onCompileAndLoad
}: StrategyDraftPreviewProps) {
  const interpretation = strategyInterpretation(draft);
  const warnings = Array.from(new Set([...responseWarnings, ...draft.warnings, ...(compileResponse?.warnings ?? [])]));
  const unsupported = Array.from(new Set([...responseUnsupported, ...draft.unsupported, ...(compileResponse?.unsupported ?? [])]));
  const validationErrors = Array.from(new Set([...responseValidationErrors, ...(compileResponse?.validation_errors ?? [])]));
  const canCompile = draft.status === "ready";

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-lab-border bg-lab-surface p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusTone(draft.status)}`}>
              {draft.status === "ready" ? <CheckCircle2 size={14} /> : <HelpCircle size={14} />}
              {labelize(draft.status)}
            </div>
            <h2 className="mt-4 text-xl font-semibold text-lab-text">Generated Strategy Draft</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-lab-secondary">
              Review the inferred workflow and assumptions before loading this into an existing form. Compilation returns inert API request JSON only.
            </p>
          </div>
          <button
            type="button"
            onClick={onCompileAndLoad}
            disabled={!canCompile || isCompiling}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-lab-blue px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
            title={canCompile ? "Compile and load the generated request" : "Resolve draft issues before compiling"}
          >
            <ClipboardList size={16} />
            {isCompiling ? "Compiling..." : `Load into ${modeLabel(draft.target_mode)}`}
          </button>
        </div>

        {loadMessage ? <p className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">{loadMessage}</p> : null}
        {compileError ? <p className="mt-4 rounded-lg border border-lab-red/40 bg-lab-red/10 px-3 py-2 text-sm text-red-100">{compileError}</p> : null}
      </section>

      <section className="grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
        <Detail label="Target Mode" value={modeLabel(draft.target_mode)} />
        <Detail label="Ticker / Dates" value={`${draft.ticker ?? "Ticker needed"} / ${draft.start_date ?? "default start"} to ${draft.end_date ?? "default end"}`} />
        <Detail label="Strategy" value={labelize(draft.strategy_kind)} />
        <Detail label="Confidence" value={draft.confidence === null ? "Not provided" : formatDecimal(draft.confidence)} />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="rounded-xl border border-lab-border bg-lab-surface p-5">
          <h3 className="text-sm font-semibold text-lab-text">Auditable Interpretation</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <Detail label="Parameters" value={jsonLabel(draft.parameters)} />
            <Detail label="Parameter Grid" value={gridLabel(draft.parameter_grid)} />
            {draft.strategy_kind === "rule_based" ? <Detail label="Rule Spec" value="Constrained DSL" /> : null}
            <Detail label="Entry" value={interpretation.entry} />
            <Detail label="Exit" value={interpretation.exit} />
            <Detail label="Sizing" value={`${labelize(draft.position_size_method)} / ${draft.position_size_value === null ? "default" : formatNumber(draft.position_size_value)}`} />
            <Detail label="Costs" value={`Commission ${draft.commission_rate ?? "default"} / slippage ${draft.slippage_bps ?? "default"} bps`} />
            <Detail label="Benchmark" value={draft.benchmark ? "Enabled" : "Disabled"} />
            <Detail label="Initial Cash" value={draft.initial_cash === null ? "Default" : formatCurrency(draft.initial_cash)} />
          </div>
        </div>

        <div className="space-y-5">
          <StrategyAssumptions title="Assumptions" items={draft.assumptions} />
          <StrategyAssumptions title="Warnings" items={warnings} tone="warning" />
          <StrategyUnsupportedState unsupported={unsupported} validationErrors={validationErrors} />
        </div>
      </section>
    </div>
  );
}
