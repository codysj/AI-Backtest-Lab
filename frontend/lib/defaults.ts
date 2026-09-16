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
  position_size_method: "PERCENT_EQUITY",
  position_size_value: 0.95,
  stop_loss_pct: null,
  take_profit_pct: null,
  trailing_stop_pct: null,
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
    fast_window: [5, 10, 20],
    slow_window: [50, 100, 200]
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

// Used only until GET /api/strategies responds; the API registry is authoritative.
export const FALLBACK_STRATEGIES: StrategyMetadata[] = [
  {
    id: "momentum",
    name: "Momentum SMA Crossover",
    description: "Buys when the fast SMA crosses above the slow SMA and sells on the reverse cross.",
    parameters: [
      { name: "fast_window", type: "integer", default: 10, min: 1, label: "Fast Window", grid: [5, 10, 20] },
      { name: "slow_window", type: "integer", default: 50, min: 2, label: "Slow Window", grid: [50, 100, 200] }
    ]
  }
];
