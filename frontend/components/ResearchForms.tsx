"use client";

import { RotateCcw, Search, SplitSquareHorizontal } from "lucide-react";
import type {
  GridSearchRequest,
  OptimizationMetric,
  PositionSizeMethod,
  ResearchStrategyId,
  StrategyMetadata,
  WalkForwardRequest
} from "../lib/types";
import type { FormErrors } from "../lib/validation";
import { RiskExitFields } from "./RiskExitFields";

type SharedProps = {
  strategies: StrategyMetadata[];
  errors: FormErrors;
  isLoading: boolean;
};

type GridSearchFormProps = SharedProps & {
  request: GridSearchRequest;
  onChange: (request: GridSearchRequest) => void;
  onSubmit: () => void;
  onReset: () => void;
};

type WalkForwardFormProps = SharedProps & {
  request: WalkForwardRequest;
  onChange: (request: WalkForwardRequest) => void;
  onSubmit: () => void;
  onReset: () => void;
};

const metricOptions: { value: OptimizationMetric; label: string }[] = [
  { value: "sharpe_ratio", label: "Sharpe" },
  { value: "sortino_ratio", label: "Sortino" },
  { value: "total_return", label: "Total return" },
  { value: "annualized_return", label: "Annualized return" },
  { value: "max_drawdown", label: "Max drawdown" },
  { value: "information_ratio", label: "Information ratio" },
  { value: "profit_factor", label: "Profit factor" },
  { value: "win_rate", label: "Win rate" }
];

const sizingOptions: { value: PositionSizeMethod; label: string }[] = [
  { value: "FIXED_DOLLAR", label: "Fixed dollar" },
  { value: "FIXED_QUANTITY", label: "Fixed quantity" },
  { value: "ALL_IN", label: "All in" },
  { value: "PERCENT_EQUITY", label: "Percent equity" },
  { value: "VOLATILITY_TARGET", label: "Volatility target" }
];

function FieldError({ message }: { message?: string }) {
  return message ? <p className="mt-1 text-xs text-lab-red">{message}</p> : null;
}

function parseRange(value: string): number[] {
  return value
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item));
}

function rangeText(values: number[] | undefined): string {
  return (values ?? []).join(", ");
}

function strategyGrid(strategy: StrategyMetadata | undefined): Record<string, number[]> {
  return Object.fromEntries((strategy?.parameters ?? []).map((parameter) => [parameter.name, parameter.grid ?? [parameter.default]]));
}

function BaseResearchFields<T extends GridSearchRequest | WalkForwardRequest>({
  request,
  strategies,
  errors,
  onChange
}: SharedProps & {
  request: T;
  onChange: (request: T) => void;
}) {
  function update<K extends keyof T>(key: K, value: T[K]) {
    onChange({ ...request, [key]: value });
  }

  function changeStrategy(strategy: ResearchStrategyId) {
    onChange({ ...request, strategy, parameter_grid: strategyGrid(strategies.find((item) => item.id === strategy)) });
  }

  function updateRange(name: string, value: string) {
    onChange({
      ...request,
      parameter_grid: {
        ...request.parameter_grid,
        [name]: parseRange(value)
      }
    });
  }

  const researchStrategies = strategies.filter((item) => item.id !== "rule_based");
  const selectedStrategy = researchStrategies.find((item) => item.id === request.strategy);

  return (
    <>
      <div className="rounded-xl border border-lab-border bg-lab-surface p-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-lab-secondary">Research Setup</h3>
        <p className="mt-2 text-xs leading-5 text-lab-muted">
          Results are computed by FastAPI and the Python engine. The browser renders returned research tables and charts only.
        </p>
        <div className="mt-4 space-y-3">
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Ticker</span>
            <input
              value={request.ticker}
              onChange={(event) => update("ticker", event.target.value.toUpperCase() as T[keyof T])}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            />
            <FieldError message={errors.ticker} />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm font-medium text-lab-text">Start</span>
              <input
                type="date"
                value={request.start_date}
                onChange={(event) => update("start_date", event.target.value as T[keyof T])}
                className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
              />
              <FieldError message={errors.start_date ?? errors.date_range} />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-lab-text">End</span>
              <input
                type="date"
                value={request.end_date}
                onChange={(event) => update("end_date", event.target.value as T[keyof T])}
                className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
              />
            </label>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-lab-border bg-lab-surface p-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-lab-secondary">Strategy Grid</h3>
        <label className="mt-4 block">
          <span className="text-sm font-medium text-lab-text">Strategy</span>
          <select
            value={request.strategy}
            onChange={(event) => changeStrategy(event.target.value as ResearchStrategyId)}
            className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
          >
            {researchStrategies.map((strategy) => (
              <option key={strategy.id} value={strategy.id}>
                {strategy.name}
              </option>
            ))}
          </select>
        </label>
        <div className="mt-3 space-y-3">
          {selectedStrategy?.parameters.map((parameter) => (
            <label key={parameter.name} className="block">
              <span className="text-sm font-medium text-lab-text">{parameter.label} Range</span>
              <input
                value={rangeText(request.parameter_grid[parameter.name])}
                onChange={(event) => updateRange(parameter.name, event.target.value)}
                className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
                placeholder="5, 10, 15"
              />
              <FieldError message={errors[`parameter_grid.${parameter.name}`]} />
            </label>
          ))}
        </div>
        <label className="mt-3 block">
          <span className="text-sm font-medium text-lab-text">Optimize</span>
          <select
            value={request.optimization_metric}
            onChange={(event) => update("optimization_metric", event.target.value as T[keyof T])}
            className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
          >
            {metricOptions.map((metric) => (
              <option key={metric.value} value={metric.value}>
                {metric.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="rounded-xl border border-lab-border bg-lab-surface p-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-lab-secondary">Portfolio And Costs</h3>
        <div className="mt-4 space-y-3">
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Initial Cash</span>
            <input
              type="number"
              value={request.initial_cash}
              onChange={(event) => update("initial_cash", Number(event.target.value) as T[keyof T])}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Position Sizing</span>
            <select
              value={request.position_size_method}
              onChange={(event) => update("position_size_method", event.target.value as T[keyof T])}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            >
              {sizingOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm font-medium text-lab-text">Size Value</span>
              <input
                type="number"
                value={request.position_size_value}
                onChange={(event) => update("position_size_value", Number(event.target.value) as T[keyof T])}
                className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-lab-text">Slippage bps</span>
              <input
                type="number"
                value={request.slippage_bps}
                onChange={(event) => update("slippage_bps", Number(event.target.value) as T[keyof T])}
                className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
              />
            </label>
          </div>
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Commission</span>
            <input
              type="number"
              step={0.0001}
              value={request.commission_rate}
              onChange={(event) => update("commission_rate", Number(event.target.value) as T[keyof T])}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            />
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-lab-border bg-lab-bg px-3 py-2 text-sm text-lab-secondary">
            <input
              type="checkbox"
              checked={request.benchmark}
              onChange={(event) => update("benchmark", event.target.checked as T[keyof T])}
              className="h-4 w-4 rounded border-lab-border bg-lab-bg accent-lab-blue"
            />
            Include benchmark analytics
          </label>
        </div>
      </div>

      <RiskExitFields value={request} errors={errors} onChange={(exits) => onChange({ ...request, ...exits })} />
    </>
  );
}

export function GridSearchForm({ request, strategies, errors, isLoading, onChange, onSubmit, onReset }: GridSearchFormProps) {
  function submitForm(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={submitForm} className="space-y-5">
      <BaseResearchFields request={request} strategies={strategies} errors={errors} isLoading={isLoading} onChange={onChange} />
      <div className="rounded-xl border border-lab-border bg-lab-surface p-4">
        <label className="block">
          <span className="text-sm font-medium text-lab-text">Top Results</span>
          <input
            type="number"
            min={1}
            max={250}
            value={request.max_results}
            onChange={(event) => onChange({ ...request, max_results: Number(event.target.value) })}
            className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
          />
          <FieldError message={errors.max_results} />
        </label>
      </div>
      <ActionButtons isLoading={isLoading} onReset={onReset} label="Run Grid Search" icon="grid" />
    </form>
  );
}

export function WalkForwardForm({ request, strategies, errors, isLoading, onChange, onSubmit, onReset }: WalkForwardFormProps) {
  function submitForm(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={submitForm} className="space-y-5">
      <BaseResearchFields request={request} strategies={strategies} errors={errors} isLoading={isLoading} onChange={onChange} />
      <div className="rounded-xl border border-lab-border bg-lab-surface p-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-lab-secondary">Fold Windows</h3>
        <div className="mt-4 grid grid-cols-3 gap-3">
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Train</span>
            <input
              type="number"
              value={request.train_window_bars}
              onChange={(event) => onChange({ ...request, train_window_bars: Number(event.target.value) })}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            />
            <FieldError message={errors.train_window_bars} />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Test</span>
            <input
              type="number"
              value={request.test_window_bars}
              onChange={(event) => onChange({ ...request, test_window_bars: Number(event.target.value) })}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            />
            <FieldError message={errors.test_window_bars} />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Step</span>
            <input
              type="number"
              value={request.step_bars}
              onChange={(event) => onChange({ ...request, step_bars: Number(event.target.value) })}
              className="mt-2 w-full rounded-lg border border-lab-border bg-lab-bg px-3 py-2 font-mono-finance text-sm text-lab-text outline-none transition focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
            />
            <FieldError message={errors.step_bars} />
          </label>
        </div>
      </div>
      <ActionButtons isLoading={isLoading} onReset={onReset} label="Run Walk Forward" icon="walk" />
    </form>
  );
}

function ActionButtons({
  isLoading,
  onReset,
  label,
  icon
}: {
  isLoading: boolean;
  onReset: () => void;
  label: string;
  icon: "grid" | "walk";
}) {
  const Icon = icon === "grid" ? Search : SplitSquareHorizontal;
  return (
    <div className="grid grid-cols-[1fr_auto] gap-3">
      <button
        type="submit"
        disabled={isLoading}
        className="inline-flex items-center justify-center gap-2 rounded-lg bg-lab-blue px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-950/30 transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <Icon size={16} />
        {isLoading ? "Running..." : label}
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
  );
}
