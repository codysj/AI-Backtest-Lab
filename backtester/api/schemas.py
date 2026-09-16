"""Pydantic schemas for the Backtester API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backtester.engine import ExecutionPolicy, PositionSizeMethod
from backtester.strategy.registry import STRATEGIES
from backtester.strategy.rule_schema import RuleBasedStrategySpec


# Kept as literals so OpenAPI and the frontend see a closed set; a test asserts
# they match backtester.strategy.registry.STRATEGIES.
ResearchStrategyId = Literal["momentum", "mean_reversion", "rsi_reversion", "donchian_breakout", "macd_crossover"]
StrategyId = Literal["momentum", "mean_reversion", "rsi_reversion", "donchian_breakout", "macd_crossover", "rule_based"]
RiskExitPct = Field(default=None, gt=0, lt=1)
ParameterType = Literal["integer", "number"]
OptimizationMetric = Literal[
    "total_return",
    "annualized_return",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "information_ratio",
    "profit_factor",
    "win_rate",
]


class StrategyParameterSchema(BaseModel):
    """Metadata for one configurable strategy parameter."""

    name: str
    type: ParameterType
    default: int | float
    min: int | float
    label: str
    grid: list[int | float] = Field(default_factory=list)


class StrategyMetadata(BaseModel):
    """Strategy metadata exposed to the frontend."""

    id: StrategyId
    name: str
    description: str
    parameters: list[StrategyParameterSchema]


class StrategiesResponse(BaseModel):
    """Response containing available strategies."""

    strategies: list[StrategyMetadata]


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str


class BacktestRequest(BaseModel):
    """Backtest request submitted by the frontend."""

    ticker: str = Field(..., min_length=1)
    start_date: str = Field(..., min_length=1)
    end_date: str = Field(..., min_length=1)
    strategy: StrategyId
    initial_cash: float = Field(default=100_000.0, gt=0)
    commission_rate: float = Field(default=0.001, ge=0)
    slippage_bps: float = Field(default=5.0, ge=0)
    execution_policy: ExecutionPolicy = ExecutionPolicy.CLOSE_SIGNAL_NEXT_OPEN
    position_size_method: PositionSizeMethod = PositionSizeMethod.PERCENT_EQUITY
    position_size_value: float = Field(default=0.95, gt=0)
    stop_loss_pct: float | None = RiskExitPct
    take_profit_pct: float | None = RiskExitPct
    trailing_stop_pct: float | None = RiskExitPct
    benchmark: bool = True
    parameters: dict[str, int | float] = Field(default_factory=dict)
    rule_spec: RuleBasedStrategySpec | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_strategy_parameters(self) -> "BacktestRequest":
        params = self.parameters
        if self.strategy == "rule_based":
            if self.rule_spec is None:
                msg = "rule_spec is required for rule_based strategy."
                raise ValueError(msg)
            if params:
                msg = "rule_based strategy does not accept numeric parameters."
                raise ValueError(msg)
            return self

        if self.rule_spec is not None:
            msg = "rule_spec is only supported for rule_based strategy."
            raise ValueError(msg)

        STRATEGIES[self.strategy].build(params)
        return self


class ResearchBaseRequest(BaseModel):
    """Shared request fields for single-asset research workflows."""

    ticker: str = Field(..., min_length=1)
    start_date: str = Field(..., min_length=1)
    end_date: str = Field(..., min_length=1)
    initial_cash: float = Field(default=100_000.0, gt=0)
    commission_rate: float = Field(default=0.001, ge=0)
    slippage_bps: float = Field(default=5.0, ge=0)
    execution_policy: ExecutionPolicy = ExecutionPolicy.CLOSE_SIGNAL_NEXT_OPEN
    position_size_method: PositionSizeMethod = PositionSizeMethod.PERCENT_EQUITY
    position_size_value: float = Field(default=0.95, gt=0)
    stop_loss_pct: float | None = RiskExitPct
    take_profit_pct: float | None = RiskExitPct
    trailing_stop_pct: float | None = RiskExitPct
    benchmark: bool = True
    strategy: ResearchStrategyId
    parameter_grid: dict[str, list[int | float]] = Field(default_factory=dict)
    optimization_metric: OptimizationMetric = "sharpe_ratio"

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_research_request(self) -> "ResearchBaseRequest":
        if self.start_date >= self.end_date:
            msg = "start_date must be before end_date."
            raise ValueError(msg)
        if not self.parameter_grid:
            msg = "parameter_grid must include at least one parameter range."
            raise ValueError(msg)

        for name, values in self.parameter_grid.items():
            if not values:
                msg = f"parameter_grid.{name} must not be empty."
                raise ValueError(msg)
            for value in values:
                numeric_value = float(value)
                if numeric_value <= 0:
                    msg = f"parameter_grid.{name} values must be positive."
                    raise ValueError(msg)

        expected = STRATEGIES[self.strategy].parameter_names
        provided = set(self.parameter_grid)
        unexpected = provided - expected
        missing = expected - provided
        if unexpected:
            msg = f"Unsupported parameter(s) for {self.strategy}: {', '.join(sorted(unexpected))}."
            raise ValueError(msg)
        if missing:
            msg = f"Missing parameter range(s) for {self.strategy}: {', '.join(sorted(missing))}."
            raise ValueError(msg)
        return self


class GridSearchRequest(ResearchBaseRequest):
    """Grid-search request submitted by the frontend."""

    max_results: int = Field(default=25, ge=1, le=250)


class WalkForwardRequest(ResearchBaseRequest):
    """Walk-forward request submitted by the frontend."""

    train_window_bars: int = Field(default=252, ge=20)
    test_window_bars: int = Field(default=63, ge=5)
    step_bars: int = Field(default=63, ge=1)

    @model_validator(mode="after")
    def validate_windows(self) -> "WalkForwardRequest":
        if self.train_window_bars <= self.test_window_bars:
            msg = "train_window_bars must be greater than test_window_bars."
            raise ValueError(msg)
        return self


class BacktestSummary(BaseModel):
    """Summary values shown above the dashboard charts."""

    strategy_name: str
    ticker: str
    initial_value: float
    final_value: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    alpha: float | None = None
    beta: float | None = None
    information_ratio: float | None = None
    total_trades: int


class SeriesPoint(BaseModel):
    """Date/value point for line charts."""

    date: str
    value: float


class RiskAnalytics(BaseModel):
    """Additional risk analytics derived server-side from a backtest."""

    best_day: float
    worst_day: float
    drawdown_duration_days: int
    value_at_risk_95: float
    conditional_value_at_risk_95: float
    rolling_sharpe: list[SeriesPoint]
    rolling_volatility: list[SeriesPoint]
    rolling_drawdown: list[SeriesPoint]
    monthly_returns: list[dict[str, int | float]]


class PricePoint(BaseModel):
    """Close price point for price charts."""

    date: str
    close: float


class TradeSchema(BaseModel):
    """Executed trade exposed to the frontend."""

    ticker: str
    side: str
    quantity: int
    price: float
    commission: float
    timestamp: str


class DecisionSchema(BaseModel):
    """A strategy decision and the latest information it could observe."""

    decision_id: str
    ticker: str
    signal: str
    decision_time: str
    information_cutoff: str
    reason: str = ""


class OrderSchema(BaseModel):
    """An order submitted from a strategy decision."""

    order_id: str
    decision_id: str
    ticker: str
    side: str
    quantity: int
    submitted_at: str


class FillSchema(BaseModel):
    """A fill linked to its submitted order."""

    order_id: str
    ticker: str
    side: str
    quantity: int
    reference_price: float
    price: float
    commission: float
    filled_at: str


class OrderEventSchema(BaseModel):
    """An order lifecycle transition."""

    order_id: str
    status: str
    timestamp: str
    reason: str


class BacktestSeries(BaseModel):
    """All chart series returned for a backtest."""

    equity: list[SeriesPoint]
    benchmark: list[SeriesPoint]
    drawdown: list[SeriesPoint]
    price: list[PricePoint]


class BacktestResponse(BaseModel):
    """Backtest response consumed by the dashboard."""

    config: dict[str, object]
    summary: BacktestSummary
    series: BacktestSeries
    trades: list[TradeSchema]
    decisions: list[DecisionSchema] = Field(default_factory=list)
    orders: list[OrderSchema] = Field(default_factory=list)
    fills: list[FillSchema] = Field(default_factory=list)
    order_events: list[OrderEventSchema] = Field(default_factory=list)
    risk: RiskAnalytics | None = None


class GridSearchRow(BaseModel):
    """One ranked grid-search row."""

    rank: int | None
    parameters: dict[str, int | float]
    final_value: float | None
    total_return: float | None
    annualized_return: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown: float | None
    information_ratio: float | None = None
    benchmark_total_return: float | None = None
    excess_total_return: float | None = None
    profit_factor: float | None
    win_rate: float | None
    total_trades: int
    error: str | None = None


class HeatmapPoint(BaseModel):
    """Heatmap-ready metric value for two numeric parameter dimensions."""

    x_param: str
    y_param: str
    x: int | float
    y: int | float
    value: float | None
    parameters: dict[str, int | float]


class RobustnessAnalysis(BaseModel):
    """Deterministic research-aid warnings for grid-search results."""

    robustness_score: float
    warnings: list[str]
    notes: list[str]
    nearby_parameter_stability: float | None = None
    trade_count_flags: list[str]
    drawdown_flags: list[str]
    overfit_risk_flags: list[str]


class GridSearchResponse(BaseModel):
    """Grid-search response consumed by Backtest Lab."""

    config: dict[str, object]
    strategy_id: ResearchStrategyId
    strategy_name: str
    optimization_metric: OptimizationMetric
    total_combinations: int
    results: list[GridSearchRow]
    failed_combinations: list[GridSearchRow]
    best_parameters: dict[str, int | float] | None
    best_row: GridSearchRow | None
    heatmap: list[HeatmapPoint]
    analysis: RobustnessAnalysis


class WalkForwardFold(BaseModel):
    """One walk-forward train/test fold."""

    fold: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    selected_parameters: dict[str, int | float]
    train_metrics: GridSearchRow | None
    test_metrics: GridSearchRow | None
    degradation_ratio: float | None
    warnings: list[str]


class WalkForwardSummary(BaseModel):
    """Aggregate walk-forward validation summary."""

    average_train_metric: float | None
    average_test_metric: float | None
    average_degradation: float | None
    number_of_folds: int
    parameter_stability: float | None
    warnings: list[str]


class WalkForwardResponse(BaseModel):
    """Walk-forward validation response consumed by Backtest Lab."""

    config: dict[str, object]
    strategy_id: ResearchStrategyId
    strategy_name: str
    optimization_metric: OptimizationMetric
    folds: list[WalkForwardFold]
    summary: WalkForwardSummary


class ErrorResponse(BaseModel):
    """Readable API error response."""

    detail: str
