export type StrategyId =
  | "momentum"
  | "mean_reversion"
  | "rsi_reversion"
  | "donchian_breakout"
  | "macd_crossover"
  | "rule_based";
export type ResearchStrategyId = Exclude<StrategyId, "rule_based">;

export type PositionSizeMethod =
  | "FIXED_DOLLAR"
  | "FIXED_QUANTITY"
  | "ALL_IN"
  | "PERCENT_EQUITY"
  | "VOLATILITY_TARGET";

export type ExecutionPolicy = "CLOSE_SIGNAL_NEXT_OPEN" | "SAME_CLOSE";

export type StrategyParameter = {
  name: string;
  type: "integer" | "number";
  default: number;
  min: number;
  label: string;
  grid?: number[];
};

export type StrategyMetadata = {
  id: StrategyId;
  name: string;
  description: string;
  parameters: StrategyParameter[];
};

export type RiskExitSettings = {
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
  trailing_stop_pct?: number | null;
};

export type BacktestRequest = RiskExitSettings & {
  ticker: string;
  start_date: string;
  end_date: string;
  strategy: StrategyId;
  initial_cash: number;
  commission_rate: number;
  slippage_bps: number;
  execution_policy: ExecutionPolicy;
  position_size_method: PositionSizeMethod;
  position_size_value: number;
  benchmark: boolean;
  parameters: Record<string, number>;
  rule_spec?: RuleBasedStrategySpec | null;
};

export type OptimizationMetric =
  | "total_return"
  | "annualized_return"
  | "sharpe_ratio"
  | "sortino_ratio"
  | "max_drawdown"
  | "information_ratio"
  | "profit_factor"
  | "win_rate";

export type ParameterGrid = Record<string, number[]>;

export type ResearchBaseRequest = Omit<BacktestRequest, "parameters" | "strategy" | "rule_spec"> & {
  strategy: ResearchStrategyId;
  parameter_grid: ParameterGrid;
  optimization_metric: OptimizationMetric;
};

export type GridSearchRequest = ResearchBaseRequest & {
  max_results: number;
};

export type WalkForwardRequest = ResearchBaseRequest & {
  train_window_bars: number;
  test_window_bars: number;
  step_bars: number;
};

export type AiTargetMode = "single_run" | "grid_search" | "walk_forward" | "unspecified";

export type AiStrategyDraftStatus = "ready" | "needs_clarification" | "unsupported";

export type AiStrategyKind = StrategyId | "unsupported";

export type IndicatorName =
  | "close"
  | "sma"
  | "rolling_high"
  | "rolling_low"
  | "bollinger_upper"
  | "bollinger_lower"
  | "ema"
  | "rsi"
  | "value";

export type ConditionOperator = ">" | "<" | ">=" | "<=" | "crosses_above" | "crosses_below";

export type IndicatorSpec = {
  name: IndicatorName;
  window?: number | null;
  num_std?: number | null;
  value?: number | null;
};

export type ConditionSpec = {
  left: IndicatorSpec;
  operator: ConditionOperator;
  right: IndicatorSpec;
};

export type RuleBasedStrategySpec = {
  rules: {
    entry: ConditionSpec[];
    exit: ConditionSpec[];
  };
};

export type StrategyDraftRequest = {
  prompt: string;
  provider?: string | null;
  model?: string | null;
  current_config?: Record<string, unknown> | null;
};

export type StrategyDraft = {
  target_mode: AiTargetMode;
  ticker: string | null;
  start_date: string | null;
  end_date: string | null;
  benchmark: boolean;
  initial_cash: number | null;
  commission_rate: number | null;
  slippage_bps: number | null;
  position_size_method: PositionSizeMethod | null;
  position_size_value: number | null;
  strategy_kind: AiStrategyKind;
  parameters: Record<string, number>;
  rule_spec: RuleBasedStrategySpec | null;
  parameter_grid: ParameterGrid | null;
  optimization_metric: OptimizationMetric | null;
  train_window_bars: number | null;
  test_window_bars: number | null;
  step_bars: number | null;
  assumptions: string[];
  warnings: string[];
  unsupported: string[];
  confidence: number | null;
  status: AiStrategyDraftStatus;
};

export type StrategyDraftResponse = {
  draft: StrategyDraft | null;
  status: AiStrategyDraftStatus;
  warnings: string[];
  unsupported: string[];
  validation_errors: string[];
};

export type StrategyCompileRequest = {
  draft: StrategyDraft;
};

export type StrategyCompilePayload = BacktestRequest | GridSearchRequest | WalkForwardRequest;

export type StrategyCompileResponse = {
  target_mode: AiTargetMode;
  status: AiStrategyDraftStatus;
  payload: StrategyCompilePayload | null;
  assumptions: string[];
  warnings: string[];
  unsupported: string[];
  validation_errors: string[];
};

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export type ResearchStatus = "awaiting_approval" | "completed" | "blocked" | "drafted";

export type ResearchStep =
  | "interpret_research_goal"
  | "draft_strategy"
  | "validate_draft"
  | "compile_request"
  | "await_user_approval"
  | "run_workflow"
  | "analyze_results"
  | "recommend_next_step";

export type ApprovedAction = "run_backtest" | "run_grid_search" | "run_walk_forward";

export type AuditEvent = {
  step: ResearchStep;
  message: string;
};

export type WorkflowResultSummary = {
  target_mode: AiTargetMode;
  status: string;
  summary: Record<string, JsonValue>;
  warnings: string[];
};

export type ResearchPlanRequest = {
  user_goal: string;
  current_config?: Record<string, JsonValue> | null;
  context?: Record<string, JsonValue> | null;
};

export type ResearchGraphResponse = {
  session_id: string;
  user_goal: string;
  status: ResearchStatus;
  current_step: ResearchStep;
  target_mode: AiTargetMode | null;
  steps: ResearchStep[];
  draft: StrategyDraft | null;
  compile_response: StrategyCompileResponse | null;
  compile_payload: StrategyCompilePayload | null;
  approval_required: boolean;
  approved_action: ApprovedAction | null;
  workflow_result: WorkflowResultSummary | null;
  analysis: string[];
  recommendation: string | null;
  warnings: string[];
  unsupported: string[];
  validation_errors: string[];
  audit_log: AuditEvent[];
};

export type ResearchApprovalRequest = {
  state: ResearchGraphResponse;
  approved_action: ApprovedAction;
};

export type HealthResponse = {
  status: string;
};

export type BacktestSummary = {
  strategy_name: string;
  ticker: string;
  initial_value: number;
  final_value: number;
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  alpha: number | null;
  beta: number | null;
  information_ratio: number | null;
  total_trades: number;
};

export type SeriesPoint = {
  date: string;
  value: number;
};

export type PricePoint = {
  date: string;
  close: number;
};

export type Trade = {
  ticker: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  commission: number;
  timestamp: string;
};

export type Decision = {
  decision_id: string;
  ticker: string;
  signal: "BUY" | "SELL" | "HOLD";
  decision_time: string;
  information_cutoff: string;
};

export type SubmittedOrder = {
  order_id: string;
  decision_id: string;
  ticker: string;
  side: "BUY" | "SELL";
  quantity: number;
  submitted_at: string;
};

export type Fill = {
  order_id: string;
  ticker: string;
  side: "BUY" | "SELL";
  quantity: number;
  reference_price: number;
  price: number;
  commission: number;
  filled_at: string;
};

export type OrderEvent = {
  order_id: string;
  status: "SUBMITTED" | "FILLED" | "REJECTED" | "EXPIRED";
  timestamp: string;
  reason: string;
};

export type BacktestResponse = {
  config: Record<string, unknown>;
  summary: BacktestSummary;
  series: {
    equity: SeriesPoint[];
    benchmark: SeriesPoint[];
    drawdown: SeriesPoint[];
    price: PricePoint[];
  };
  trades: Trade[];
  decisions: Decision[];
  orders: SubmittedOrder[];
  fills: Fill[];
  order_events: OrderEvent[];
  risk: RiskAnalytics | null;
};

export type RiskAnalytics = {
  best_day: number;
  worst_day: number;
  drawdown_duration_days: number;
  value_at_risk_95: number;
  conditional_value_at_risk_95: number;
  rolling_sharpe: SeriesPoint[];
  rolling_volatility: SeriesPoint[];
  rolling_drawdown: SeriesPoint[];
  monthly_returns: { year: number; month: number; return: number }[];
};

export type GridSearchRow = {
  rank: number | null;
  parameters: Record<string, number>;
  final_value: number | null;
  total_return: number | null;
  annualized_return: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number | null;
  information_ratio: number | null;
  benchmark_total_return: number | null;
  excess_total_return: number | null;
  profit_factor: number | null;
  win_rate: number | null;
  total_trades: number;
  error: string | null;
};

export type HeatmapPoint = {
  x_param: string;
  y_param: string;
  x: number;
  y: number;
  value: number | null;
  parameters: Record<string, number>;
};

export type RobustnessAnalysis = {
  robustness_score: number;
  warnings: string[];
  notes: string[];
  nearby_parameter_stability: number | null;
  trade_count_flags: string[];
  drawdown_flags: string[];
  overfit_risk_flags: string[];
};

export type GridSearchResponse = {
  config: Record<string, unknown>;
  strategy_id: ResearchStrategyId;
  strategy_name: string;
  optimization_metric: OptimizationMetric;
  total_combinations: number;
  results: GridSearchRow[];
  failed_combinations: GridSearchRow[];
  best_parameters: Record<string, number> | null;
  best_row: GridSearchRow | null;
  heatmap: HeatmapPoint[];
  analysis: RobustnessAnalysis;
};

export type WalkForwardFold = {
  fold: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  selected_parameters: Record<string, number>;
  train_metrics: GridSearchRow | null;
  test_metrics: GridSearchRow | null;
  degradation_ratio: number | null;
  warnings: string[];
};

export type WalkForwardSummary = {
  average_train_metric: number | null;
  average_test_metric: number | null;
  average_degradation: number | null;
  number_of_folds: number;
  parameter_stability: number | null;
  warnings: string[];
};

export type WalkForwardResponse = {
  config: Record<string, unknown>;
  strategy_id: ResearchStrategyId;
  strategy_name: string;
  optimization_metric: OptimizationMetric;
  folds: WalkForwardFold[];
  summary: WalkForwardSummary;
};
