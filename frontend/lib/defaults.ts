import type { BacktestRequest, GridSearchRequest, StrategyMetadata, WalkForwardRequest } from "./types";

export const DEFAULT_BACKTEST_REQUEST: BacktestRequest = {
  ticker: "AAPL",
  start_date: "2018-01-01",
  end_date: "2023-12-31",
  strategy: "momentum",
  initial_cash: 100000,
  commission_rate: 0.001,
  slippage_bps: 5,
  execution_policy: "CLOSE_SIGNAL_NEXT_OPEN",
  position_size_method: "FIXED_DOLLAR",
  position_size_value: 10000,
  benchmark: true,
  parameters: {
    fast_window: 10,
    slow_window: 50
  },
  rule_spec: null
};

export const DEFAULT_GRID_SEARCH_REQUEST: GridSearchRequest = {
  ...DEFAULT_BACKTEST_REQUEST,
  strategy: "momentum",
  parameter_grid: {
    fast_window: [5, 10, 15],
    slow_window: [30, 50, 80]
  },
  optimization_metric: "sharpe_ratio",
  max_results: 25
};

export const DEFAULT_WALK_FORWARD_REQUEST: WalkForwardRequest = {
  ...DEFAULT_GRID_SEARCH_REQUEST,
  train_window_bars: 252,
  test_window_bars: 63,
  step_bars: 63
};

export const FALLBACK_STRATEGIES: StrategyMetadata[] = [
  {
    id: "momentum",
    name: "Momentum SMA Crossover",
    description: "Uses fast and slow moving average crossovers to generate buy/sell signals.",
    parameters: [
      { name: "fast_window", type: "integer", default: 10, min: 1, label: "Fast Window" },
      { name: "slow_window", type: "integer", default: 50, min: 2, label: "Slow Window" }
    ]
  },
  {
    id: "mean_reversion",
    name: "Mean Reversion",
    description: "Uses Bollinger-style bands to identify overextended prices.",
    parameters: [
      { name: "window", type: "integer", default: 20, min: 1, label: "Window" },
      { name: "num_std", type: "number", default: 2, min: 0.1, label: "Standard Deviations" }
    ]
  },
  {
    id: "rule_based",
    name: "Generated Rule-Based Strategy",
    description: "Runs a constrained AI Builder rule set. Use AI Builder to create or load the rule spec.",
    parameters: []
  }
];
