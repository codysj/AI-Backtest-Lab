"""Service helpers for the FastAPI layer."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from numbers import Real

import pandas as pd

from backtester.api.schemas import (
    BacktestRequest,
    BacktestResponse,
    BacktestSeries,
    BacktestSummary,
    DecisionSchema,
    FillSchema,
    GridSearchRequest,
    GridSearchResponse,
    GridSearchRow,
    HeatmapPoint,
    OptimizationMetric,
    OrderEventSchema,
    OrderSchema,
    PricePoint,
    ResearchBaseRequest,
    RiskAnalytics,
    RobustnessAnalysis,
    SeriesPoint,
    StrategyMetadata,
    StrategyParameterSchema,
    TradeSchema,
    WalkForwardFold,
    WalkForwardRequest,
    WalkForwardResponse,
    WalkForwardSummary,
)
from backtester.data.loader import DataLoader
from backtester.engine import BacktestConfig, BacktestEngine
from backtester.metrics import (
    best_worst_day,
    buy_and_hold_equity,
    conditional_value_at_risk,
    drawdown_duration_days,
    generate_report,
    monthly_returns,
    rolling_drawdown,
    rolling_sharpe_ratio,
    rolling_volatility,
    value_at_risk,
)
from backtester.portfolio import Trade
from backtester.research import run_grid_search
from backtester.strategy import MeanReversionStrategy, MomentumStrategy, RuleBasedStrategy, Strategy
from backtester.strategy.rule_schema import RuleBasedStrategySpec


@dataclass
class StaticDataLoader(DataLoader):
    """DataLoader adapter that slices already-fetched deterministic data."""

    data: pd.DataFrame

    def fetch(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        del ticker
        sliced = self.data.loc[pd.Timestamp(start) : pd.Timestamp(end)]
        if sliced.empty:
            msg = f"No price data available between {start} and {end}."
            raise ValueError(msg)
        return sliced.copy()


def available_strategies() -> list[StrategyMetadata]:
    """Return supported strategy metadata for the frontend."""
    return [
        StrategyMetadata(
            id="momentum",
            name="Momentum SMA Crossover",
            description="Uses fast and slow moving average crossovers to generate buy/sell signals.",
            parameters=[
                StrategyParameterSchema(name="fast_window", type="integer", default=10, min=1, label="Fast Window"),
                StrategyParameterSchema(name="slow_window", type="integer", default=50, min=2, label="Slow Window"),
            ],
        ),
        StrategyMetadata(
            id="mean_reversion",
            name="Mean Reversion",
            description="Uses Bollinger-style bands to identify overextended prices.",
            parameters=[
                StrategyParameterSchema(name="window", type="integer", default=20, min=1, label="Window"),
                StrategyParameterSchema(name="num_std", type="number", default=2.0, min=0.1, label="Standard Deviations"),
            ],
        ),
        StrategyMetadata(
            id="rule_based",
            name="Generated Rule-Based Strategy",
            description="Runs a constrained AI Builder rule set. Use AI Builder to create or load the rule spec.",
            parameters=[],
        ),
    ]


def build_strategy(
    strategy_id: str,
    parameters: dict[str, int | float],
    rule_spec: RuleBasedStrategySpec | None = None,
) -> Strategy:
    """Build a Strategy instance from API request parameters."""
    if strategy_id == "momentum":
        return MomentumStrategy(
            fast_window=int(parameters.get("fast_window", 10)),
            slow_window=int(parameters.get("slow_window", 50)),
        )
    if strategy_id == "mean_reversion":
        return MeanReversionStrategy(
            window=int(parameters.get("window", 20)),
            num_std=float(parameters.get("num_std", 2.0)),
        )
    if strategy_id == "rule_based":
        if rule_spec is None:
            msg = "rule_spec is required for rule_based strategy."
            raise ValueError(msg)
        return RuleBasedStrategy(rule_spec)
    msg = f"Unsupported strategy: {strategy_id}"
    raise ValueError(msg)


def run_backtest_from_request(request: BacktestRequest) -> BacktestResponse:
    """Run a single-asset backtest and convert it into an API response."""
    loader = DataLoader()
    config = BacktestConfig(
        ticker=request.ticker,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_cash=request.initial_cash,
        commission_rate=request.commission_rate,
        slippage_bps=request.slippage_bps,
        position_size_method=request.position_size_method,
        position_size_value=request.position_size_value,
        execution_policy=request.execution_policy,
    )
    strategy = build_strategy(request.strategy, request.parameters, request.rule_spec)
    result = BacktestEngine(loader=loader, strategy=strategy, config=config).run()
    price_data = loader.fetch(config.ticker, config.start_date, config.end_date)
    benchmark = buy_and_hold_equity(price_data, config.initial_cash) if request.benchmark else None
    report = generate_report(result, benchmark_equity=benchmark)

    return BacktestResponse(
        config={
            "ticker": config.ticker,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "initial_cash": config.initial_cash,
            "commission_rate": config.commission_rate,
            "slippage_bps": config.slippage_bps,
            "execution_policy": config.execution_policy.value,
            "position_size_method": config.position_size_method.value,
            "position_size_value": config.position_size_value,
            "strategy": request.strategy,
            "parameters": request.parameters,
            "rule_spec": request.rule_spec.model_dump(mode="json") if request.rule_spec is not None else None,
            "benchmark": request.benchmark,
        },
        summary=BacktestSummary(
            strategy_name=result.strategy_name,
            ticker=config.ticker,
            initial_value=result.initial_value,
            final_value=result.final_value,
            total_return=_float_report_value(report, "total_return"),
            annualized_return=_float_report_value(report, "annualized_return"),
            sharpe_ratio=_float_report_value(report, "sharpe_ratio"),
            sortino_ratio=_float_report_value(report, "sortino_ratio"),
            max_drawdown=_float_report_value(report, "max_drawdown"),
            win_rate=_float_report_value(report, "win_rate"),
            profit_factor=_finite_float_report_value(report, "profit_factor"),
            alpha=_optional_report_value(report, "alpha"),
            beta=_optional_report_value(report, "beta"),
            information_ratio=_optional_report_value(report, "information_ratio"),
            total_trades=len(result.trades),
        ),
        series=BacktestSeries(
            equity=convert_equity_series(result.equity_curve),
            benchmark=convert_equity_series(benchmark) if benchmark is not None else [],
            drawdown=compute_drawdown_series(result.equity_curve),
            price=convert_price_data(price_data),
        ),
        trades=convert_trades(result.trades),
        decisions=[
            DecisionSchema(
                decision_id=item.decision_id,
                ticker=item.ticker,
                signal=item.signal,
                decision_time=item.decision_time.isoformat(),
                information_cutoff=item.information_cutoff.isoformat(),
            )
            for item in result.decisions
        ],
        orders=[
            OrderSchema(
                order_id=item.order_id,
                decision_id=item.decision_id,
                ticker=item.ticker,
                side=item.side.value,
                quantity=item.quantity,
                submitted_at=item.timestamp.isoformat(),
            )
            for item in result.orders
        ],
        fills=[
            FillSchema(
                order_id=item.order_id,
                ticker=item.ticker,
                side=item.side.value,
                quantity=item.quantity,
                reference_price=item.reference_price,
                price=item.price,
                commission=item.commission,
                filled_at=item.filled_at.isoformat(),
            )
            for item in result.fills
        ],
        order_events=[
            OrderEventSchema(
                order_id=item.order_id,
                status=item.status.value,
                timestamp=item.timestamp.isoformat(),
                reason=item.reason,
            )
            for item in result.order_events
        ],
        risk=build_risk_analytics(result.equity_curve),
    )


def run_grid_search_from_request(request: GridSearchRequest) -> GridSearchResponse:
    """Run a grid search and convert ranked results into an API response."""
    loader = DataLoader()
    price_data = loader.fetch(request.ticker, request.start_date, request.end_date)
    static_loader = StaticDataLoader(price_data)
    frame = _run_grid_frame(request, request.start_date, request.end_date, static_loader)
    return _grid_response_from_frame(request, frame)


def run_walk_forward_from_request(request: WalkForwardRequest) -> WalkForwardResponse:
    """Run single-asset walk-forward validation through server-side engines."""
    loader = DataLoader()
    price_data = loader.fetch(request.ticker, request.start_date, request.end_date)
    if len(price_data) < request.train_window_bars + request.test_window_bars:
        msg = "Not enough bars for the requested train/test windows."
        raise ValueError(msg)

    static_loader = StaticDataLoader(price_data)
    folds: list[WalkForwardFold] = []
    start_index = 0
    fold_number = 1
    metric = request.optimization_metric
    while start_index + request.train_window_bars + request.test_window_bars <= len(price_data):
        train_slice = price_data.iloc[start_index : start_index + request.train_window_bars]
        test_slice = price_data.iloc[
            start_index + request.train_window_bars : start_index + request.train_window_bars + request.test_window_bars
        ]
        train_start = _index_date(train_slice.index[0])
        train_end = _index_date(train_slice.index[-1])
        test_start = _index_date(test_slice.index[0])
        test_end = _index_date(test_slice.index[-1])

        train_frame = _run_grid_frame(request, train_start, train_end, static_loader)
        train_rows = _rows_from_frame(train_frame, metric, max_results=len(train_frame))
        best_train = next((row for row in train_rows if row.error is None), None)
        warnings: list[str] = []
        test_row: GridSearchRow | None = None
        degradation: float | None = None

        if best_train is None:
            warnings.append("No valid training combination was available for this fold.")
        else:
            test_frame = _run_grid_frame_for_params(request, test_start, test_end, static_loader, best_train.parameters)
            test_rows = _rows_from_frame(test_frame, metric, max_results=1)
            test_row = test_rows[0] if test_rows else None
            degradation = _degradation_ratio(_metric_value(best_train, metric), _metric_value(test_row, metric) if test_row else None)
            if degradation is not None and degradation < 0.5:
                warnings.append("Out-of-sample metric retained less than half of the training score.")
            if test_row is not None and test_row.total_trades < 2:
                warnings.append("Test fold has very few trades.")

        folds.append(
            WalkForwardFold(
                fold=fold_number,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                selected_parameters=best_train.parameters if best_train is not None else {},
                train_metrics=best_train,
                test_metrics=test_row,
                degradation_ratio=degradation,
                warnings=warnings,
            )
        )
        fold_number += 1
        start_index += request.step_bars

    if not folds:
        msg = "No walk-forward folds could be generated for the requested windows."
        raise ValueError(msg)

    return WalkForwardResponse(
        config=_research_config(request),
        strategy_id=request.strategy,
        strategy_name=_strategy_display_name(request.strategy),
        optimization_metric=metric,
        folds=folds,
        summary=_walk_forward_summary(folds, metric),
    )


def convert_equity_series(series: pd.Series) -> list[SeriesPoint]:
    """Convert a pandas Series into chart points."""
    return [
        SeriesPoint(date=pd.Timestamp(str(index)).date().isoformat(), value=float(value))
        for index, value in series.items()
    ]


def build_risk_analytics(equity_curve: pd.Series) -> RiskAnalytics:
    """Build richer risk analytics from server-side return and drawdown math."""
    returns = equity_curve.pct_change().dropna()
    best_day, worst_day = best_worst_day(returns)
    monthly = monthly_returns(equity_curve)
    return RiskAnalytics(
        best_day=best_day,
        worst_day=worst_day,
        drawdown_duration_days=drawdown_duration_days(equity_curve),
        value_at_risk_95=value_at_risk(returns, confidence=0.95),
        conditional_value_at_risk_95=conditional_value_at_risk(returns, confidence=0.95),
        rolling_sharpe=convert_equity_series(rolling_sharpe_ratio(returns)),
        rolling_volatility=convert_equity_series(rolling_volatility(returns)),
        rolling_drawdown=convert_equity_series(rolling_drawdown(equity_curve)),
        monthly_returns=[
            {"year": int(row["year"]), "month": int(row["month"]), "return": float(row["return"])}
            for _, row in monthly.iterrows()
        ],
    )


def _run_grid_frame(
    request: ResearchBaseRequest,
    start_date: str,
    end_date: str,
    loader: DataLoader,
) -> pd.DataFrame:
    config = _backtest_config_from_research_request(request, start_date, end_date)
    return run_grid_search(
        loader=loader,
        strategy_factory=_strategy_factory(request.strategy),
        param_grid=request.parameter_grid,
        config=config,
        sort_by=request.optimization_metric,
        ascending=False,
        benchmark=request.benchmark,
    )


def _run_grid_frame_for_params(
    request: ResearchBaseRequest,
    start_date: str,
    end_date: str,
    loader: DataLoader,
    parameters: dict[str, int | float],
) -> pd.DataFrame:
    one_value_grid = {key: [value] for key, value in parameters.items()}
    config = _backtest_config_from_research_request(request, start_date, end_date)
    return run_grid_search(
        loader=loader,
        strategy_factory=_strategy_factory(request.strategy),
        param_grid=one_value_grid,
        config=config,
        sort_by=request.optimization_metric,
        ascending=False,
        benchmark=request.benchmark,
    )


def _grid_response_from_frame(request: GridSearchRequest, frame: pd.DataFrame) -> GridSearchResponse:
    rows = _rows_from_frame(frame, request.optimization_metric, max_results=request.max_results)
    failed_rows = [row for row in _rows_from_frame(frame, request.optimization_metric, max_results=len(frame)) if row.error is not None]
    best_row = next((row for row in rows if row.error is None), None)
    return GridSearchResponse(
        config=_research_config(request) | {"max_results": request.max_results},
        strategy_id=request.strategy,
        strategy_name=_strategy_display_name(request.strategy),
        optimization_metric=request.optimization_metric,
        total_combinations=len(frame),
        results=rows,
        failed_combinations=failed_rows,
        best_parameters=best_row.parameters if best_row is not None else None,
        best_row=best_row,
        heatmap=_heatmap_points(frame, request.parameter_grid, request.optimization_metric),
        analysis=_robustness_analysis(frame, request.optimization_metric),
    )


def _rows_from_frame(frame: pd.DataFrame, metric: OptimizationMetric, max_results: int) -> list[GridSearchRow]:
    rows: list[GridSearchRow] = []
    for index, (_, row) in enumerate(frame.head(max_results).iterrows(), start=1):
        error = _string_or_none(row.get("error"))
        rows.append(
            GridSearchRow(
                rank=index if error is None else None,
                parameters=_row_parameters(row),
                final_value=_optional_float(row.get("final_value")),
                total_return=_optional_float(row.get("total_return")),
                annualized_return=_optional_float(row.get("annualized_return")),
                sharpe_ratio=_optional_float(row.get("sharpe_ratio")),
                sortino_ratio=_optional_float(row.get("sortino_ratio")),
                max_drawdown=_optional_float(row.get("max_drawdown")),
                information_ratio=_optional_float(row.get("information_ratio")),
                benchmark_total_return=_optional_float(row.get("benchmark_total_return")),
                excess_total_return=_optional_float(row.get("excess_total_return")),
                profit_factor=_optional_float(row.get("profit_factor")),
                win_rate=_optional_float(row.get("win_rate")),
                total_trades=int(row.get("total_trades", 0)),
                error=error,
            )
        )
    if metric == "max_drawdown":
        return sorted(rows, key=lambda item: _metric_sort_value(item, metric), reverse=True)
    return rows


def _robustness_analysis(frame: pd.DataFrame, metric: OptimizationMetric) -> RobustnessAnalysis:
    """Score grid-search stability with deterministic heuristics, not prediction."""
    valid = frame[frame["error"].fillna("") == ""].copy()
    failed_count = len(frame) - len(valid)
    warnings: list[str] = []
    notes: list[str] = ["Heuristics are a research aid, not a guarantee of future performance."]
    trade_flags: list[str] = []
    drawdown_flags: list[str] = []
    overfit_flags: list[str] = []
    score = 100.0
    stability: float | None = None

    if failed_count:
        warning = f"{failed_count} parameter combination(s) failed."
        warnings.append(warning)
        overfit_flags.append(warning)
        score -= min(25.0, failed_count / max(len(frame), 1) * 40.0)
    if valid.empty:
        warnings.append("No valid parameter combinations were available.")
        return RobustnessAnalysis(
            robustness_score=0.0,
            warnings=warnings,
            notes=notes,
            nearby_parameter_stability=None,
            trade_count_flags=trade_flags,
            drawdown_flags=drawdown_flags,
            overfit_risk_flags=overfit_flags,
        )

    best = valid.iloc[0]
    best_metric = _optional_float(best.get(metric))
    if int(best.get("total_trades", 0)) < 4:
        warning = "Best result has very few trades."
        warnings.append(warning)
        trade_flags.append(warning)
        score -= 20.0
    max_dd = _optional_float(best.get("max_drawdown"))
    if max_dd is not None and max_dd <= -0.3:
        warning = "Best result has severe max drawdown."
        warnings.append(warning)
        drawdown_flags.append(warning)
        score -= 18.0
    total_return_value = _optional_float(best.get("total_return"))
    if total_return_value is not None and total_return_value > 1.0 and max_dd is not None and max_dd <= -0.25:
        warning = "Extreme return is paired with high drawdown."
        warnings.append(warning)
        overfit_flags.append(warning)
        score -= 12.0
    excess = _optional_float(best.get("excess_total_return"))
    if excess is not None and excess < 0:
        warning = "Best standalone result lagged the benchmark on total return."
        warnings.append(warning)
        overfit_flags.append(warning)
        score -= 10.0

    if len(valid) >= 3 and best_metric is not None:
        top_count = max(1, math.ceil(len(valid) * 0.2))
        top_metric = valid.head(top_count)[metric].dropna()
        all_metric = valid[metric].dropna()
        if not top_metric.empty and not all_metric.empty:
            stability = float(top_metric.mean() / best_metric) if best_metric not in (0.0, None) else 0.0
            stability = max(0.0, min(1.0, stability))
            if stability < 0.65:
                warning = "Performance appears concentrated in a small set of configurations."
                warnings.append(warning)
                overfit_flags.append(warning)
                score -= 18.0
            notes.append(f"Top-parameter stability is {stability:.2f}.")

    return RobustnessAnalysis(
        robustness_score=max(0.0, min(100.0, score)),
        warnings=warnings,
        notes=notes,
        nearby_parameter_stability=stability,
        trade_count_flags=trade_flags,
        drawdown_flags=drawdown_flags,
        overfit_risk_flags=overfit_flags,
    )


def _heatmap_points(
    frame: pd.DataFrame,
    parameter_grid: dict[str, list[int | float]],
    metric: OptimizationMetric,
) -> list[HeatmapPoint]:
    varied = [name for name, values in parameter_grid.items() if len(set(values)) > 1]
    if len(varied) != 2:
        return []
    x_param, y_param = varied
    points: list[HeatmapPoint] = []
    for _, row in frame.iterrows():
        points.append(
            HeatmapPoint(
                x_param=x_param,
                y_param=y_param,
                x=_cell_number(row[x_param]),
                y=_cell_number(row[y_param]),
                value=_optional_float(row.get(metric)),
                parameters=_row_parameters(row),
            )
        )
    return points


def _walk_forward_summary(folds: list[WalkForwardFold], metric: OptimizationMetric) -> WalkForwardSummary:
    train_values = [_metric_value(fold.train_metrics, metric) for fold in folds]
    test_values = [_metric_value(fold.test_metrics, metric) for fold in folds]
    degradations = [fold.degradation_ratio for fold in folds if fold.degradation_ratio is not None]
    parameter_sets = [tuple(sorted(fold.selected_parameters.items())) for fold in folds if fold.selected_parameters]
    warnings: list[str] = []
    if test_values and sum(1 for value in test_values if value is not None and value < 0) > len(test_values) / 2:
        warnings.append("Most test folds produced negative optimization metrics.")
    if parameter_sets and len(set(parameter_sets)) == len(parameter_sets) and len(parameter_sets) > 1:
        warnings.append("Selected parameters changed in every fold.")
    if degradations and sum(1 for value in degradations if value < 0.5) > len(degradations) / 2:
        warnings.append("Most folds showed substantial out-of-sample degradation.")

    return WalkForwardSummary(
        average_train_metric=_average([value for value in train_values if value is not None]),
        average_test_metric=_average([value for value in test_values if value is not None]),
        average_degradation=_average(degradations),
        number_of_folds=len(folds),
        parameter_stability=_parameter_stability(parameter_sets),
        warnings=warnings,
    )


def compute_drawdown_series(equity_curve: pd.Series) -> list[SeriesPoint]:
    """Compute drawdown chart points from an equity curve."""
    if equity_curve.empty:
        return []
    rolling_max = equity_curve.cummax()
    safe_rolling_max = rolling_max.mask(rolling_max == 0)
    drawdown = ((equity_curve - safe_rolling_max) / safe_rolling_max).fillna(0.0)
    return convert_equity_series(drawdown)


def convert_trades(trades: list[Trade]) -> list[TradeSchema]:
    """Convert engine trades into API trade records."""
    return [
        TradeSchema(
            ticker=trade.ticker,
            side=trade.side.value,
            quantity=trade.quantity,
            price=trade.price,
            commission=trade.commission,
            timestamp=trade.timestamp.date().isoformat(),
        )
        for trade in trades
    ]


def convert_price_data(data: pd.DataFrame) -> list[PricePoint]:
    """Convert price data into close-price chart points."""
    return [
        PricePoint(date=pd.Timestamp(str(index)).date().isoformat(), close=float(row["close"]))
        for index, row in data.iterrows()
    ]


def _float_report_value(report: dict[str, object], key: str) -> float:
    value = report[key]
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _finite_float_report_value(report: dict[str, object], key: str) -> float:
    value = _float_report_value(report, key)
    if math.isfinite(value):
        return value
    return 0.0


def _optional_report_value(report: dict[str, object], key: str) -> float | None:
    if key not in report:
        return None
    value = _float_report_value(report, key)
    return value if math.isfinite(value) else None


def _backtest_config_from_research_request(
    request: ResearchBaseRequest,
    start_date: str,
    end_date: str,
) -> BacktestConfig:
    return BacktestConfig(
        ticker=request.ticker,
        start_date=start_date,
        end_date=end_date,
        initial_cash=request.initial_cash,
        commission_rate=request.commission_rate,
        slippage_bps=request.slippage_bps,
        position_size_method=request.position_size_method,
        position_size_value=request.position_size_value,
        execution_policy=request.execution_policy,
    )


def _research_config(request: ResearchBaseRequest) -> dict[str, object]:
    return {
        "ticker": request.ticker,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "initial_cash": request.initial_cash,
        "commission_rate": request.commission_rate,
        "slippage_bps": request.slippage_bps,
        "execution_policy": request.execution_policy.value,
        "position_size_method": request.position_size_method.value,
        "position_size_value": request.position_size_value,
        "strategy": request.strategy,
        "parameter_grid": request.parameter_grid,
        "optimization_metric": request.optimization_metric,
        "benchmark": request.benchmark,
    }


def _strategy_factory(strategy_id: str) -> type[Strategy]:
    if strategy_id == "momentum":
        return MomentumStrategy
    if strategy_id == "mean_reversion":
        return MeanReversionStrategy
    msg = f"Unsupported strategy: {strategy_id}"
    raise ValueError(msg)


def _strategy_display_name(strategy_id: str) -> str:
    strategy = next((item for item in available_strategies() if item.id == strategy_id), None)
    return strategy.name if strategy is not None else strategy_id


def _row_parameters(row: pd.Series) -> dict[str, int | float]:
    parameters: dict[str, int | float] = {}
    for key in ["fast_window", "slow_window", "window", "num_std"]:
        if key in row.index and not pd.isna(row[key]):
            value = row[key]
            if isinstance(value, Real):
                parameters[key] = _response_number(value, field_name=key)
    return parameters


def _cell_number(value: object) -> int | float:
    return _response_number(value, field_name="heatmap parameter value")


def _response_number(value: object, *, field_name: str) -> int | float:
    if not isinstance(value, Real):
        msg = f"{field_name} must be numeric."
        raise TypeError(msg)
    as_float = float(value)
    return int(as_float) if as_float.is_integer() else as_float


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Real):
        as_float = float(value)
        return as_float if math.isfinite(as_float) else None
    return None


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _metric_value(row: GridSearchRow | None, metric: OptimizationMetric) -> float | None:
    if row is None:
        return None
    values: dict[OptimizationMetric, float | None] = {
        "total_return": row.total_return,
        "annualized_return": row.annualized_return,
        "sharpe_ratio": row.sharpe_ratio,
        "sortino_ratio": row.sortino_ratio,
        "max_drawdown": row.max_drawdown,
        "information_ratio": row.information_ratio,
        "profit_factor": row.profit_factor,
        "win_rate": row.win_rate,
    }
    return values[metric]


def _metric_sort_value(row: GridSearchRow, metric: OptimizationMetric) -> float:
    value = _metric_value(row, metric)
    if value is None:
        return float("-inf")
    return value


def _degradation_ratio(train_value: float | None, test_value: float | None) -> float | None:
    if train_value is None or test_value is None or train_value == 0:
        return None
    return test_value / train_value


def _index_date(value: object) -> str:
    if isinstance(value, pd.Timestamp):
        timestamp = value
    elif isinstance(value, datetime | date | str | int | float):
        timestamp = pd.Timestamp(value)
    else:
        msg = "Index values must be date-like."
        raise TypeError(msg)
    return timestamp.date().isoformat()


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _parameter_stability(parameter_sets: list[tuple[tuple[str, int | float], ...]]) -> float | None:
    if not parameter_sets:
        return None
    most_common = max(parameter_sets.count(item) for item in set(parameter_sets))
    return most_common / len(parameter_sets)
