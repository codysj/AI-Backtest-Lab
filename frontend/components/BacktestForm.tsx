"use client";

import { Play, RotateCcw, SlidersHorizontal } from "lucide-react";
import { useMemo } from "react";
import { conditionLabel } from "../lib/rules";
import type { BacktestRequest, ExecutionPolicy, PositionSizeMethod, StrategyId, StrategyMetadata } from "../lib/types";
import type { FormErrors } from "../lib/validation";
import { RiskExitFields } from "./RiskExitFields";

type BacktestFormProps = {
  request: BacktestRequest;
  strategies: StrategyMetadata[];
  errors: FormErrors;
  isLoading: boolean;
  onChange: (request: BacktestRequest) => void;
  onSubmit: () => void;
  onReset: () => void;
};

const methodOptions: { value: PositionSizeMethod; label: string; helper: string }[] = [
  { value: "FIXED_DOLLAR", label: "Fixed dollar", helper: "Allocate a dollar amount per signal." },
  { value: "FIXED_QUANTITY", label: "Fixed quantity", helper: "Buy or sell a fixed share count." },
  { value: "ALL_IN", label: "All in", helper: "Use available cash on buy signals." },
  { value: "PERCENT_EQUITY", label: "Percent equity", helper: "Fraction of equity per buy, e.g. 0.95." },
  { value: "VOLATILITY_TARGET", label: "Volatility target", helper: "Daily risk fraction scaled by realized volatility." }
];

function FieldError({ message }: { message?: string }) {
  if (!message) {
    return null;
  }
  return <p className="mt-1 text-xs text-lab-red">{message}</p>;
}

function SectionHeading({ title, kicker }: { title: string; kicker?: string }) {
  return (
    <div className="mb-3">
      <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-lab-secondary">{title}</h3>
      {kicker ? <p className="mt-1 text-xs leading-5 text-lab-muted">{kicker}</p> : null}
    </div>
  );
}

export function BacktestForm({
  request,
  strategies,
  errors,
  isLoading,
  onChange,
  onSubmit,
  onReset
}: BacktestFormProps) {
  const selectedStrategy = useMemo(
    () => strategies.find((strategy) => strategy.id === request.strategy),
    [request.strategy, strategies]
  );

  function update<K extends keyof BacktestRequest>(key: K, value: BacktestRequest[K]) {
    onChange({ ...request, [key]: value });
  }

  function updateParameter(name: string, value: number) {
    onChange({
      ...request,
      parameters: {
        ...request.parameters,
        [name]: value
      }
    });
  }

  function changeStrategy(strategyId: StrategyId) {
    const strategy = strategies.find((item) => item.id === strategyId);
    const parameters: Record<string, number> = {};
    strategy?.parameters.forEach((parameter) => {
      parameters[parameter.name] = Number(parameter.default);
    });
    onChange({
      ...request,
      strategy: strategyId,
      parameters,
      rule_spec: null
    });
  }

  function submitForm(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  const sizingHelper = methodOptions.find((option) => option.value === request.position_size_method)?.helper;

  return (
    <form onSubmit={submitForm} className="space-y-5">
      <div className="rounded-xl border border-lab-border bg-lab-surface p-4">
        <div className="mb-4 flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-lab-border bg-lab-card text-lab-cyan">
            <SlidersHorizontal size={17} />
          </div>
          <p className="text-sm leading-6 text-lab-secondary">
            Configure a strategy, run the engine, then inspect equity, drawdown, trades, and risk metrics.
          </p>
        </div>

        <SectionHeading title="Universe" />
        <div className="space-y-3">
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Ticker</span>
            <input
              value={request.ticker}
              onChange={(event) => update("ticker", event.target.value.toUpperCase())}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
              placeholder="AAPL"
            />
            <FieldError message={errors.ticker} />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm font-medium text-lab-text">Start</span>
              <input
                type="date"
                value={request.start_date}
                onChange={(event) => update("start_date", event.target.value)}
                className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
              />
              <FieldError message={errors.start_date ?? errors.date_range} />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-lab-text">End</span>
              <input
                type="date"
                value={request.end_date}
                onChange={(event) => update("end_date", event.target.value)}
                className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
              />
              <FieldError message={errors.end_date} />
            </label>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-lab-border bg-lab-surface p-4">
        <SectionHeading title="Strategy" kicker={selectedStrategy?.description} />
        <label className="block">
          <span className="text-sm font-medium text-lab-text">Model</span>
          <select
            value={request.strategy}
            onChange={(event) => changeStrategy(event.target.value as StrategyId)}
            className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
          >
            {strategies.map((strategy) => (
              <option key={strategy.id} value={strategy.id}>
                {strategy.name}
              </option>
            ))}
          </select>
        </label>

        <div className="mt-3 grid grid-cols-2 gap-3">
          {selectedStrategy?.parameters.map((parameter) => (
            <label key={parameter.name} className="block">
              <span className="text-sm font-medium text-lab-text">{parameter.label}</span>
              <input
                type="number"
                min={parameter.min}
                step={parameter.type === "integer" ? 1 : 0.1}
                value={request.parameters[parameter.name] ?? parameter.default}
                onChange={(event) => updateParameter(parameter.name, Number(event.target.value))}
                className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
              />
              <FieldError message={errors[`parameters.${parameter.name}`]} />
            </label>
          ))}
        </div>
        {request.strategy === "rule_based" ? (
          <div className="mt-3 rounded-lg border border-lab-border bg-lab-bg p-3">
            <div className="text-xs uppercase tracking-[0.16em] text-lab-muted">Rule Set</div>
            {request.rule_spec ? (
              <div className="mt-2 space-y-2 font-mono-finance text-xs leading-5 text-lab-secondary">
                <p>Entry: {request.rule_spec.rules.entry.map(conditionLabel).join(" AND ")}</p>
                <p>Exit: {request.rule_spec.rules.exit.map(conditionLabel).join(" OR ")}</p>
              </div>
            ) : (
              <p className="mt-2 text-sm leading-6 text-lab-secondary">Load a generated rule-based draft from AI Builder.</p>
            )}
            <FieldError message={errors.rule_spec} />
          </div>
        ) : null}
      </div>

      <div className="rounded-xl border border-lab-border bg-lab-surface p-4">
        <SectionHeading title="Portfolio" />
        <div className="space-y-3">
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Execution Timing</span>
            <select
              value={request.execution_policy}
              onChange={(event) => update("execution_policy", event.target.value as ExecutionPolicy)}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            >
              <option value="CLOSE_SIGNAL_NEXT_OPEN">Close signal → next open</option>
              <option value="SAME_CLOSE">Same close (optimistic)</option>
            </select>
            <p className="mt-1 text-xs leading-5 text-lab-muted">
              Signals use data through the current close. Next-open execution is the defensible default.
            </p>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-lab-text">Initial Cash</span>
            <input
              type="number"
              min={1}
              value={request.initial_cash}
              onChange={(event) => update("initial_cash", Number(event.target.value))}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            />
            <FieldError message={errors.initial_cash} />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-lab-text">Position Sizing</span>
            <select
              value={request.position_size_method}
              onChange={(event) => update("position_size_method", event.target.value as PositionSizeMethod)}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            >
              {methodOptions.map((method) => (
                <option key={method.value} value={method.value}>
                  {method.label}
                </option>
              ))}
            </select>
            {sizingHelper ? <p className="mt-1 text-xs leading-5 text-lab-muted">{sizingHelper}</p> : null}
          </label>

          <label className="block">
            <span className="text-sm font-medium text-lab-text">Size Value</span>
            <input
              type="number"
              min={0.0001}
              step={0.0001}
              value={request.position_size_value}
              onChange={(event) => update("position_size_value", Number(event.target.value))}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            />
            <FieldError message={errors.position_size_value} />
          </label>
        </div>
      </div>

      <RiskExitFields value={request} errors={errors} onChange={(exits) => onChange({ ...request, ...exits })} />

      <div className="rounded-xl border border-lab-border bg-lab-surface p-4">
        <SectionHeading title="Costs" />
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Commission</span>
            <input
              type="number"
              min={0}
              step={0.0001}
              value={request.commission_rate}
              onChange={(event) => update("commission_rate", Number(event.target.value))}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            />
            <FieldError message={errors.commission_rate} />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Slippage bps</span>
            <input
              type="number"
              min={0}
              value={request.slippage_bps}
              onChange={(event) => update("slippage_bps", Number(event.target.value))}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            />
            <FieldError message={errors.slippage_bps} />
          </label>
        </div>

        <label className="mt-4 flex items-center gap-3 rounded-lg border border-lab-border bg-lab-bg px-3 py-2 text-sm text-lab-secondary">
          <input
            type="checkbox"
            checked={request.benchmark}
            onChange={(event) => update("benchmark", event.target.checked)}
            className="h-4 w-4 rounded border-lab-border bg-lab-bg accent-lab-blue"
          />
          Include buy-and-hold benchmark
        </label>
      </div>

      <div className="grid grid-cols-[1fr_auto] gap-3">
        <button
          type="submit"
          disabled={isLoading}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-lab-blue px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-950/30 transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Play size={16} />
          {isLoading ? "Running..." : "Run Backtest"}
        </button>
        <button
          type="button"
          onClick={onReset}
          disabled={isLoading}
          className="inline-flex items-center justify-center rounded-lg border border-lab-border bg-lab-card px-3 text-lab-secondary transition hover:border-lab-blue hover:text-lab-text disabled:cursor-not-allowed disabled:opacity-60"
          aria-label="Reset defaults"
          title="Reset defaults"
        >
          <RotateCcw size={16} />
        </button>
      </div>
    </form>
  );
}
