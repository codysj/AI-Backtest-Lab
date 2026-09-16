"""Compile inert strategy drafts into existing API request models."""

from __future__ import annotations

from typing import Any, cast

from pydantic import ValidationError

from backtester.ai.schemas import (
    StrategyCompileResponse,
    StrategyDraft,
    StrategyDraftStatus,
    StrategyKind,
    TargetMode,
)
from backtester.ai.validator import validate_strategy_draft
from backtester.api.schemas import (
    BacktestRequest,
    GridSearchRequest,
    OptimizationMetric,
    ResearchStrategyId,
    StrategyId,
    WalkForwardRequest,
)
from backtester.engine import PositionSizeMethod
from backtester.strategy.registry import STRATEGIES


DEFAULT_START_DATE = "2020-01-01"
DEFAULT_END_DATE = "2023-12-31"
DEFAULT_OPTIMIZATION_METRIC: OptimizationMetric = "sharpe_ratio"
DEFAULT_MAX_RESULTS = 25
DEFAULT_TRAIN_WINDOW_BARS = 252
DEFAULT_TEST_WINDOW_BARS = 63
DEFAULT_STEP_BARS = 63


class DraftCompileError(ValueError):
    """Raised when an inert draft cannot be compiled into an API request."""


def compile_strategy_draft(draft: StrategyDraft) -> StrategyCompileResponse:
    """Compile a draft into an existing API-compatible request payload."""
    validation = validate_strategy_draft(draft)
    warnings = _unique_strings([*draft.warnings, *validation.warnings])
    unsupported = _unique_strings([*draft.unsupported, *validation.unsupported])
    if unsupported:
        status = (
            StrategyDraftStatus.UNSUPPORTED
            if draft.status == StrategyDraftStatus.UNSUPPORTED
            else StrategyDraftStatus.NEEDS_CLARIFICATION
        )
        return StrategyCompileResponse(
            target_mode=draft.target_mode,
            status=status,
            payload=None,
            assumptions=draft.assumptions,
            warnings=warnings,
            unsupported=unsupported,
            validation_errors=validation.errors,
        )
    if validation.errors:
        return StrategyCompileResponse(
            target_mode=draft.target_mode,
            status=StrategyDraftStatus.NEEDS_CLARIFICATION,
            payload=None,
            assumptions=draft.assumptions,
            warnings=warnings,
            unsupported=unsupported,
            validation_errors=validation.errors,
        )
    if draft.status != StrategyDraftStatus.READY:
        return StrategyCompileResponse(
            target_mode=draft.target_mode,
            status=draft.status,
            payload=None,
            assumptions=draft.assumptions,
            warnings=warnings,
            unsupported=unsupported,
            validation_errors=["Only ready drafts can be compiled."],
        )

    try:
        request, compile_warnings = _compile_request(draft)
    except DraftCompileError as exc:
        return StrategyCompileResponse(
            target_mode=draft.target_mode,
            status=StrategyDraftStatus.NEEDS_CLARIFICATION,
            payload=None,
            assumptions=draft.assumptions,
            warnings=warnings,
            unsupported=unsupported,
            validation_errors=[str(exc)],
        )

    return StrategyCompileResponse(
        target_mode=draft.target_mode,
        status=StrategyDraftStatus.READY,
        payload=request.model_dump(mode="json"),
        assumptions=draft.assumptions,
        warnings=_unique_strings([*warnings, *compile_warnings]),
        unsupported=unsupported,
        validation_errors=[],
    )


def compile_backtest_request(draft: StrategyDraft) -> BacktestRequest:
    """Compile a ready single-run draft into BacktestRequest."""
    _raise_if_not_compilable(draft, TargetMode.SINGLE_RUN)
    try:
        return BacktestRequest(
            **_base_payload(draft),
            strategy=_strategy_id(draft.strategy_kind),
            parameters=_parameters_for_single_run(draft),
            rule_spec=draft.rule_spec,
        )
    except ValidationError as exc:
        raise DraftCompileError(_validation_error_text(exc)) from exc


def compile_grid_search_request(draft: StrategyDraft) -> GridSearchRequest:
    """Compile a ready grid-search draft into GridSearchRequest."""
    _raise_if_not_compilable(draft, TargetMode.GRID_SEARCH)
    try:
        return GridSearchRequest(
            **_base_payload(draft),
            strategy=_research_strategy_id(draft.strategy_kind),
            parameter_grid=_parameter_grid_for_research(draft),
            optimization_metric=draft.optimization_metric or DEFAULT_OPTIMIZATION_METRIC,
            max_results=DEFAULT_MAX_RESULTS,
        )
    except ValidationError as exc:
        raise DraftCompileError(_validation_error_text(exc)) from exc


def compile_walk_forward_request(draft: StrategyDraft) -> WalkForwardRequest:
    """Compile a ready walk-forward draft into WalkForwardRequest."""
    _raise_if_not_compilable(draft, TargetMode.WALK_FORWARD)
    try:
        return WalkForwardRequest(
            **_base_payload(draft),
            strategy=_research_strategy_id(draft.strategy_kind),
            parameter_grid=_parameter_grid_for_research(draft),
            optimization_metric=draft.optimization_metric or DEFAULT_OPTIMIZATION_METRIC,
            train_window_bars=draft.train_window_bars or DEFAULT_TRAIN_WINDOW_BARS,
            test_window_bars=draft.test_window_bars or DEFAULT_TEST_WINDOW_BARS,
            step_bars=draft.step_bars or DEFAULT_STEP_BARS,
        )
    except ValidationError as exc:
        raise DraftCompileError(_validation_error_text(exc)) from exc


def _compile_request(draft: StrategyDraft) -> tuple[BacktestRequest | GridSearchRequest | WalkForwardRequest, list[str]]:
    warnings = _compile_warnings(draft)
    if draft.target_mode == TargetMode.SINGLE_RUN:
        return compile_backtest_request(draft), warnings
    if draft.target_mode == TargetMode.GRID_SEARCH:
        return compile_grid_search_request(draft), warnings
    if draft.target_mode == TargetMode.WALK_FORWARD:
        return compile_walk_forward_request(draft), warnings
    raise DraftCompileError("target_mode must be single_run, grid_search, or walk_forward.")


def _raise_if_not_compilable(draft: StrategyDraft, expected_mode: TargetMode) -> None:
    validation = validate_strategy_draft(draft)
    if validation.errors:
        raise DraftCompileError("; ".join(validation.errors))
    if validation.unsupported:
        raise DraftCompileError("; ".join(validation.unsupported))
    if draft.status != StrategyDraftStatus.READY:
        raise DraftCompileError("Only ready drafts can be compiled.")
    if draft.target_mode != expected_mode:
        raise DraftCompileError(f"Draft target_mode must be {expected_mode.value}.")


def _base_payload(draft: StrategyDraft) -> dict[str, Any]:
    if not draft.ticker:
        raise DraftCompileError("ticker is required.")
    return {
        "ticker": draft.ticker,
        "start_date": draft.start_date or DEFAULT_START_DATE,
        "end_date": draft.end_date or DEFAULT_END_DATE,
        "initial_cash": draft.initial_cash or 100_000.0,
        "commission_rate": draft.commission_rate if draft.commission_rate is not None else 0.001,
        "slippage_bps": draft.slippage_bps if draft.slippage_bps is not None else 5.0,
        "position_size_method": draft.position_size_method or PositionSizeMethod.PERCENT_EQUITY,
        "position_size_value": draft.position_size_value or 0.95,
        "benchmark": draft.benchmark,
    }


def _strategy_id(strategy_kind: StrategyKind) -> StrategyId:
    if strategy_kind == StrategyKind.RULE_BASED:
        return "rule_based"
    return _research_strategy_id(strategy_kind)


def _research_strategy_id(strategy_kind: StrategyKind) -> ResearchStrategyId:
    if strategy_kind == StrategyKind.RULE_BASED:
        raise DraftCompileError("rule_based drafts can only compile to single_run in v1.")
    if strategy_kind.value not in STRATEGIES:
        raise DraftCompileError(f"Unsupported strategy kind: {strategy_kind.value}.")
    return cast(ResearchStrategyId, strategy_kind.value)


def _parameters_for_single_run(draft: StrategyDraft) -> dict[str, int | float]:
    if draft.strategy_kind == StrategyKind.RULE_BASED:
        return {}
    spec = STRATEGIES[_research_strategy_id(draft.strategy_kind)]
    return {name: _required_number(draft.parameters, name) for name in sorted(spec.parameter_names)}


def _parameter_grid_for_research(draft: StrategyDraft) -> dict[str, list[int | float]]:
    if draft.parameter_grid is not None:
        return draft.parameter_grid
    return STRATEGIES[_research_strategy_id(draft.strategy_kind)].default_grid()


def _compile_warnings(draft: StrategyDraft) -> list[str]:
    warnings: list[str] = []
    if draft.start_date is None or draft.end_date is None:
        warnings.append(f"Default date range {DEFAULT_START_DATE} to {DEFAULT_END_DATE} was inferred.")
    if draft.target_mode in {TargetMode.GRID_SEARCH, TargetMode.WALK_FORWARD} and draft.parameter_grid is None:
        warnings.append("Default parameter grid ranges were inferred.")
    if draft.target_mode in {TargetMode.GRID_SEARCH, TargetMode.WALK_FORWARD} and draft.optimization_metric is None:
        warnings.append(f"Default optimization metric {DEFAULT_OPTIMIZATION_METRIC} was inferred.")
    if draft.target_mode == TargetMode.WALK_FORWARD:
        if draft.train_window_bars is None or draft.test_window_bars is None or draft.step_bars is None:
            warnings.append("Default walk-forward train/test/step windows were inferred.")
    return warnings


def _required_number(parameters: dict[str, int | float], key: str) -> int | float:
    if key not in parameters:
        raise DraftCompileError(f"{key} is required.")
    return parameters[key]


def _validation_error_text(exc: ValidationError) -> str:
    return "; ".join(str(error["msg"]) for error in exc.errors())


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique
