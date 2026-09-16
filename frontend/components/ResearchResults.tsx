"use client";

import { Download, Play } from "lucide-react";
import { useMemo, useState } from "react";
import type {
  BacktestRequest,
  GridSearchResponse,
  GridSearchRow,
  OptimizationMetric,
  WalkForwardResponse
} from "../lib/types";
import { exportConfigJson, exportGridSearchCsv } from "../lib/exports";
import { formatCurrency, formatDate, formatDecimal, formatNumber, formatPercent } from "./formatters";

type GridSearchResultsProps = {
  result: GridSearchResponse | null;
  isLoading: boolean;
  error: string | null;
  onRunSelected: (request: BacktestRequest) => void;
};

type WalkForwardResultsProps = {
  result: WalkForwardResponse | null;
  isLoading: boolean;
  error: string | null;
};

function metricLabel(metric: OptimizationMetric): string {
  return metric.replaceAll("_", " ");
}

function formatMetric(metric: OptimizationMetric, value: number | null | undefined): string {
  if (value === null || value === undefined) return "n/a";
  if (["total_return", "annualized_return", "max_drawdown", "win_rate"].includes(metric)) {
    return formatPercent(value);
  }
  return formatDecimal(value);
}

function parametersLabel(parameters: Record<string, number>): string {
  return Object.entries(parameters)
    .map(([key, value]) => `${key.replaceAll("_", " ")} ${formatNumber(value)}`)
    .join(" / ");
}

function rowMetric(row: GridSearchRow | null, metric: OptimizationMetric): number | null {
  if (!row) return null;
  return row[metric];
}

function StateFrame({ title, message }: { title: string; message: string }) {
  return (
    <section className="rounded-xl border border-lab-border bg-lab-surface p-6">
      <h2 className="text-base font-semibold text-lab-text">{title}</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-lab-secondary">{message}</p>
    </section>
  );
}

export function GridSearchResults({ result, isLoading, error, onRunSelected }: GridSearchResultsProps) {
  const [selectedRank, setSelectedRank] = useState<number | null>(null);
  const selectedRow = useMemo(() => {
    if (!result) return null;
    return result.results.find((row) => row.rank === selectedRank) ?? result.best_row;
  }, [result, selectedRank]);

  if (isLoading && !result) {
    return <StateFrame title="Grid Search Running" message="Evaluating each parameter combination through the Python engine." />;
  }
  if (!result) {
    return (
      <div className="space-y-5">
        {error ? <StateFrame title="Grid Search Error" message={error} /> : null}
        <StateFrame title="Grid Search" message="Sweep parameter ranges, rank configurations, inspect robustness warnings, then promote a selected row into the single-run workflow." />
      </div>
    );
  }

  const selectedConfig = selectedRow
    ? ({
        ticker: String(result.config.ticker),
        start_date: String(result.config.start_date),
        end_date: String(result.config.end_date),
        strategy: result.strategy_id,
        initial_cash: Number(result.config.initial_cash),
        commission_rate: Number(result.config.commission_rate),
        slippage_bps: Number(result.config.slippage_bps),
        execution_policy: (result.config.execution_policy ?? "CLOSE_SIGNAL_NEXT_OPEN") as BacktestRequest["execution_policy"],
        position_size_method: result.config.position_size_method as BacktestRequest["position_size_method"],
        position_size_value: Number(result.config.position_size_value),
        benchmark: Boolean(result.config.benchmark),
        parameters: selectedRow.parameters
      } satisfies BacktestRequest)
    : null;

  return (
    <div className="space-y-5">
      {error ? <StateFrame title="Grid Search Error" message={error} /> : null}
      <section id="grid-search" className="rounded-xl border border-lab-border bg-lab-surface p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-lab-text">{result.strategy_name} Grid Search</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-lab-secondary">
              {result.total_combinations} combinations ranked by {metricLabel(result.optimization_metric)}. Robustness warnings are deterministic heuristics for research triage.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => exportGridSearchCsv(result)}
              className="inline-flex items-center gap-2 rounded-lg border border-lab-border bg-lab-card px-3 py-2 text-sm text-lab-secondary transition hover:border-lab-blue hover:text-lab-text"
            >
              <Download size={15} />
              Results CSV
            </button>
            <button
              type="button"
              onClick={() => exportConfigJson(result.config, "grid-search-config.json")}
              className="inline-flex items-center gap-2 rounded-lg border border-lab-border bg-lab-card px-3 py-2 text-sm text-lab-secondary transition hover:border-lab-blue hover:text-lab-text"
            >
              <Download size={15} />
              Config JSON
            </button>
          </div>
        </div>
      </section>

      <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
        <SummaryTile label="Best Metric" value={formatMetric(result.optimization_metric, rowMetric(result.best_row ?? selectedRow, result.optimization_metric))} />
        <SummaryTile label="Robustness" value={formatDecimal(result.analysis.robustness_score)} helper="0 to 100" />
        <SummaryTile label="Failures" value={String(result.failed_combinations.length)} helper="preserved with errors" />
        <SummaryTile label="Best Params" value={result.best_parameters ? parametersLabel(result.best_parameters) : "n/a"} />
      </div>

      {result.analysis.warnings.length > 0 ? (
        <section className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
          <h3 className="text-sm font-semibold text-amber-200">Robustness Warnings</h3>
          <ul className="mt-2 space-y-1 text-sm text-amber-100/90">
            {result.analysis.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <LeaderboardTable result={result} selectedRank={selectedRow?.rank ?? null} onSelect={(row) => setSelectedRank(row.rank)} />
        <div className="space-y-5">
          <SelectedRowPanel row={selectedRow} metric={result.optimization_metric} selectedConfig={selectedConfig} onRunSelected={onRunSelected} />
          <Heatmap result={result} />
        </div>
      </section>

      {result.failed_combinations.length > 0 ? (
        <section className="rounded-xl border border-lab-border bg-lab-card p-4">
          <h3 className="text-sm font-semibold text-lab-text">Failed Combinations</h3>
          <div className="mt-3 space-y-2">
            {result.failed_combinations.map((row, index) => (
              <div key={`${row.error}-${index}`} className="rounded-lg border border-lab-border bg-lab-bg p-3 text-sm">
                <div className="font-mono-finance text-lab-text">{parametersLabel(row.parameters)}</div>
                <div className="mt-1 text-lab-red">{row.error}</div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function SummaryTile({ label, value, helper }: { label: string; value: string; helper?: string }) {
  return (
    <div className="rounded-xl border border-lab-border bg-lab-card p-4">
      <div className="text-xs uppercase tracking-[0.16em] text-lab-muted">{label}</div>
      <div className="mt-2 font-mono-finance text-lg font-semibold text-lab-text">{value}</div>
      {helper ? <div className="mt-1 text-xs text-lab-secondary">{helper}</div> : null}
    </div>
  );
}

function LeaderboardTable({
  result,
  selectedRank,
  onSelect
}: {
  result: GridSearchResponse;
  selectedRank: number | null;
  onSelect: (row: GridSearchRow) => void;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-lab-border bg-lab-surface">
      <div className="border-b border-lab-border px-4 py-3">
        <h3 className="text-sm font-semibold text-lab-text">Leaderboard</h3>
      </div>
      <div className="max-h-[520px] overflow-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="sticky top-0 z-10 border-b border-lab-border bg-lab-card text-xs uppercase tracking-[0.16em] text-lab-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Rank</th>
              <th className="px-4 py-3 font-medium">Parameters</th>
              <th className="px-4 py-3 text-right font-medium">{metricLabel(result.optimization_metric)}</th>
              <th className="px-4 py-3 text-right font-medium">Drawdown</th>
              <th className="px-4 py-3 text-right font-medium">Trades</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-lab-border/70">
            {result.results.map((row, index) => (
              <tr
                key={`${row.rank ?? "error"}-${index}`}
                onClick={() => onSelect(row)}
                className={`cursor-pointer transition hover:bg-lab-card/70 ${row.rank === selectedRank ? "bg-lab-card" : "bg-lab-surface"}`}
              >
                <td className="px-4 py-3 font-mono-finance text-lab-secondary">{row.rank ?? "-"}</td>
                <td className="px-4 py-3 font-mono-finance text-lab-text">{parametersLabel(row.parameters)}</td>
                <td className="px-4 py-3 text-right font-mono-finance text-lab-secondary">{formatMetric(result.optimization_metric, rowMetric(row, result.optimization_metric))}</td>
                <td className="px-4 py-3 text-right font-mono-finance text-lab-secondary">{formatPercent(row.max_drawdown ?? 0)}</td>
                <td className="px-4 py-3 text-right font-mono-finance text-lab-secondary">{row.total_trades}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SelectedRowPanel({
  row,
  metric,
  selectedConfig,
  onRunSelected
}: {
  row: GridSearchRow | null;
  metric: OptimizationMetric;
  selectedConfig: BacktestRequest | null;
  onRunSelected: (request: BacktestRequest) => void;
}) {
  if (!row || !selectedConfig) {
    return null;
  }
  return (
    <section className="rounded-xl border border-lab-border bg-lab-card p-4">
      <h3 className="text-sm font-semibold text-lab-text">Selected Configuration</h3>
      <div className="mt-3 space-y-2 text-sm">
        <div className="font-mono-finance text-lab-text">{parametersLabel(row.parameters)}</div>
        <div className="text-lab-secondary">
          {metricLabel(metric)} <span className="font-mono-finance text-lab-text">{formatMetric(metric, rowMetric(row, metric))}</span>
        </div>
        <div className="text-lab-secondary">
          Final value <span className="font-mono-finance text-lab-text">{formatCurrency(row.final_value ?? 0)}</span>
        </div>
      </div>
      <button
        type="button"
        onClick={() => onRunSelected(selectedConfig)}
        className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-lab-blue px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500"
      >
        <Play size={15} />
        Run selected config
      </button>
    </section>
  );
}

function Heatmap({ result }: { result: GridSearchResponse }) {
  if (result.heatmap.length === 0) {
    return (
      <section className="rounded-xl border border-lab-border bg-lab-card p-4">
        <h3 className="text-sm font-semibold text-lab-text">Heatmap</h3>
        <p className="mt-2 text-sm leading-6 text-lab-secondary">Heatmap appears when exactly two numeric parameter ranges vary.</p>
      </section>
    );
  }
  const values = result.heatmap.map((point) => point.value).filter((value): value is number => value !== null);
  const min = Math.min(...values);
  const max = Math.max(...values);
  return (
    <section className="rounded-xl border border-lab-border bg-lab-card p-4">
      <h3 className="text-sm font-semibold text-lab-text">Heatmap</h3>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {result.heatmap.map((point) => {
          const intensity = point.value === null || max === min ? 0.25 : 0.25 + ((point.value - min) / (max - min)) * 0.65;
          return (
            <div
              key={`${point.x}-${point.y}`}
              className="rounded-lg border border-lab-border p-2 text-xs"
              style={{ backgroundColor: `rgba(59, 130, 246, ${intensity})` }}
              title={parametersLabel(point.parameters)}
            >
              <div className="font-mono-finance text-lab-text">{formatMetric(result.optimization_metric, point.value)}</div>
              <div className="mt-1 text-lab-secondary">
                {point.x_param} {point.x} / {point.y_param} {point.y}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function WalkForwardResults({ result, isLoading, error }: WalkForwardResultsProps) {
  if (isLoading && !result) {
    return <StateFrame title="Walk-Forward Running" message="Optimizing each training fold and evaluating the selected parameters out of sample." />;
  }
  if (!result) {
    return (
      <div className="space-y-5">
        {error ? <StateFrame title="Walk-Forward Error" message={error} /> : null}
        <StateFrame title="Walk-Forward Validation" message="Use rolling train/test folds to see whether grid-search choices survive outside the optimization window." />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {error ? <StateFrame title="Walk-Forward Error" message={error} /> : null}
      <section id="walk-forward" className="rounded-xl border border-lab-border bg-lab-surface p-5">
        <h2 className="text-xl font-semibold text-lab-text">{result.strategy_name} Walk-Forward</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-lab-secondary">
          {result.summary.number_of_folds} folds optimized by {metricLabel(result.optimization_metric)}, with each selected parameter set tested on the next unseen window.
        </p>
      </section>

      <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
        <SummaryTile label="Avg Train" value={formatMetric(result.optimization_metric, result.summary.average_train_metric)} />
        <SummaryTile label="Avg Test" value={formatMetric(result.optimization_metric, result.summary.average_test_metric)} />
        <SummaryTile label="Avg Degradation" value={formatDecimal(result.summary.average_degradation)} />
        <SummaryTile label="Param Stability" value={formatPercent(result.summary.parameter_stability ?? 0)} />
      </div>

      {result.summary.warnings.length > 0 ? (
        <section className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
          <h3 className="text-sm font-semibold text-amber-200">Validation Warnings</h3>
          <ul className="mt-2 space-y-1 text-sm text-amber-100/90">
            {result.summary.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-lab-border bg-lab-surface">
        <div className="border-b border-lab-border px-4 py-3">
          <h3 className="text-sm font-semibold text-lab-text">Folds</h3>
        </div>
        <div className="overflow-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-lab-border bg-lab-card text-xs uppercase tracking-[0.16em] text-lab-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Fold</th>
                <th className="px-4 py-3 font-medium">Train</th>
                <th className="px-4 py-3 font-medium">Test</th>
                <th className="px-4 py-3 font-medium">Parameters</th>
                <th className="px-4 py-3 text-right font-medium">Train Metric</th>
                <th className="px-4 py-3 text-right font-medium">Test Metric</th>
                <th className="px-4 py-3 text-right font-medium">Degradation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-lab-border/70">
              {result.folds.map((fold) => (
                <tr key={fold.fold} className="bg-lab-surface">
                  <td className="px-4 py-3 font-mono-finance text-lab-secondary">{fold.fold}</td>
                  <td className="px-4 py-3 font-mono-finance text-lab-secondary">{formatDate(fold.train_start)} to {formatDate(fold.train_end)}</td>
                  <td className="px-4 py-3 font-mono-finance text-lab-secondary">{formatDate(fold.test_start)} to {formatDate(fold.test_end)}</td>
                  <td className="px-4 py-3 font-mono-finance text-lab-text">{parametersLabel(fold.selected_parameters)}</td>
                  <td className="px-4 py-3 text-right font-mono-finance text-lab-secondary">{formatMetric(result.optimization_metric, rowMetric(fold.train_metrics, result.optimization_metric))}</td>
                  <td className="px-4 py-3 text-right font-mono-finance text-lab-secondary">{formatMetric(result.optimization_metric, rowMetric(fold.test_metrics, result.optimization_metric))}</td>
                  <td className="px-4 py-3 text-right font-mono-finance text-lab-secondary">{formatDecimal(fold.degradation_ratio)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
