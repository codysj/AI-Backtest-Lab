"""Validation helpers for inert AI strategy drafts."""

from __future__ import annotations

from datetime import date

from backtester.ai.schemas import (
    StrategyDraft,
    StrategyDraftStatus,
    StrategyDraftValidation,
    StrategyKind,
    TargetMode,
)
from backtester.strategy.registry import STRATEGIES


RAW_CODE_KEYS = frozenset(
    {
        "code",
        "raw_code",
        "python",
        "script",
        "source",
        "function",
        "callable",
        "module",
        "lambda",
        "__",
    }
)
UNSUPPORTED_CONCEPT_TERMS = (
    "broker execution",
    "live trading",
    "broker",
    "options flow",
    "twitter sentiment",
    "sentiment feed",
    "intraday",
    "minute bars",
    "filesystem",
    "file path",
    "write file",
    "multi-asset",
    "multi asset",
    "python",
    "lambda",
    "eval",
    "exec",
)


def validate_strategy_draft(draft: StrategyDraft) -> StrategyDraftValidation:
    """Validate draft semantics beyond Pydantic type checks."""
    errors: list[str] = []
    warnings: list[str] = []
    unsupported = list(draft.unsupported)
    for term in _unsupported_terms_in_draft(draft):
        if term not in unsupported:
            unsupported.append(term)

    if draft.status == StrategyDraftStatus.READY and not draft.ticker:
        errors.append("ticker is required for ready drafts.")

    start_date = _parse_date("start_date", draft.start_date, errors)
    end_date = _parse_date("end_date", draft.end_date, errors)
    if start_date is not None and end_date is not None and start_date >= end_date:
        errors.append("start_date must be before end_date.")

    _reject_raw_code_keys(draft.parameters, "parameters", errors)
    if draft.parameter_grid is not None:
        _reject_raw_code_keys(draft.parameter_grid, "parameter_grid", errors)

    if draft.strategy_kind == StrategyKind.UNSUPPORTED:
        if "Unsupported strategy or workflow." not in unsupported:
            unsupported.append("Unsupported strategy or workflow.")
    elif draft.strategy_kind == StrategyKind.MOMENTUM:
        _validate_momentum_parameters(draft, errors)
    elif draft.strategy_kind == StrategyKind.MEAN_REVERSION:
        _validate_mean_reversion_parameters(draft, errors)
    elif draft.strategy_kind.value in STRATEGIES:
        _validate_registry_parameters(draft, errors)
    elif draft.strategy_kind == StrategyKind.RULE_BASED:
        _validate_rule_based_draft(draft, errors)
    else:
        errors.append(f"Unsupported strategy kind: {draft.strategy_kind.value}.")

    if unsupported and draft.status == StrategyDraftStatus.READY:
        errors.append("ready drafts cannot include unsupported items.")
    if unsupported and not draft.warnings:
        warnings.append("Some requested ideas are unsupported by the v1 builder.")

    return StrategyDraftValidation(errors=errors, warnings=warnings, unsupported=unsupported)


def validate_strategy_draft_or_raise(draft: StrategyDraft) -> None:
    """Raise ValueError when a draft is not valid."""
    validation = validate_strategy_draft(draft)
    if validation.errors:
        raise ValueError("; ".join(validation.errors))


def _parse_date(name: str, value: str | None, errors: list[str]) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{name} must be a valid ISO date.")
        return None


def _reject_raw_code_keys(
    values: dict[str, int | float] | dict[str, list[int | float]],
    field_name: str,
    errors: list[str],
) -> None:
    blocked = sorted(key for key in values if key.lower() in RAW_CODE_KEYS)
    if blocked:
        errors.append(f"{field_name} cannot include raw code field(s): {', '.join(blocked)}.")


def _unsupported_terms_in_draft(draft: StrategyDraft) -> list[str]:
    text_parts = [
        *(draft.assumptions),
        *(draft.warnings),
        *(draft.unsupported),
    ]
    lowered = "\n".join(text_parts).lower()
    return [term for term in UNSUPPORTED_CONCEPT_TERMS if term in lowered]


def _validate_momentum_parameters(draft: StrategyDraft, errors: list[str]) -> None:
    if draft.parameters or draft.target_mode == TargetMode.SINGLE_RUN:
        fast_window = _positive_integer_parameter(draft.parameters, "fast_window", errors)
        slow_window = _positive_integer_parameter(draft.parameters, "slow_window", errors)
        if fast_window is not None and slow_window is not None and fast_window >= slow_window:
            errors.append("fast_window must be less than slow_window.")
    if draft.parameter_grid is not None:
        _validate_parameter_grid(draft.parameter_grid, {"fast_window", "slow_window"}, errors)
        _validate_momentum_grid_order(draft.parameter_grid, errors)


def _validate_mean_reversion_parameters(draft: StrategyDraft, errors: list[str]) -> None:
    if draft.parameters or draft.target_mode == TargetMode.SINGLE_RUN:
        _positive_integer_parameter(draft.parameters, "window", errors)
        num_std = draft.parameters.get("num_std")
        if num_std is None:
            errors.append("num_std is required for mean_reversion drafts.")
        elif float(num_std) <= 0:
            errors.append("num_std must be positive.")
    if draft.parameter_grid is not None:
        _validate_parameter_grid(draft.parameter_grid, {"window", "num_std"}, errors)


def _validate_registry_parameters(draft: StrategyDraft, errors: list[str]) -> None:
    spec = STRATEGIES[draft.strategy_kind.value]
    if draft.parameters or draft.target_mode == TargetMode.SINGLE_RUN:
        missing = sorted(spec.parameter_names - set(draft.parameters))
        errors.extend(f"{name} is required." for name in missing)
        if not missing:
            try:
                spec.build(draft.parameters)
            except ValueError as exc:
                errors.append(str(exc))
    if draft.parameter_grid is not None:
        _validate_parameter_grid(draft.parameter_grid, spec.parameter_names, errors)


def _validate_rule_based_draft(draft: StrategyDraft, errors: list[str]) -> None:
    if draft.rule_spec is None:
        errors.append("rule_spec is required for rule_based drafts.")
    if draft.parameters:
        errors.append("rule_based drafts cannot include numeric strategy parameters.")
    if draft.parameter_grid is not None:
        errors.append("rule_based drafts do not support parameter_grid in v1.")
    if draft.target_mode not in {TargetMode.SINGLE_RUN, TargetMode.UNSPECIFIED}:
        errors.append("rule_based drafts can only compile to single_run in v1.")


def _positive_integer_parameter(
    parameters: dict[str, int | float],
    name: str,
    errors: list[str],
) -> int | None:
    value = parameters.get(name)
    if value is None:
        errors.append(f"{name} is required.")
        return None
    numeric = float(value)
    if numeric <= 0:
        errors.append(f"{name} must be positive.")
        return None
    if not numeric.is_integer():
        errors.append(f"{name} must be an integer.")
        return None
    return int(numeric)


def _validate_parameter_grid(
    parameter_grid: dict[str, list[int | float]],
    expected_keys: set[str],
    errors: list[str],
) -> None:
    unexpected = sorted(set(parameter_grid) - expected_keys)
    if unexpected:
        errors.append(f"Unsupported parameter_grid key(s): {', '.join(unexpected)}.")
    for key, values in parameter_grid.items():
        if not values:
            errors.append(f"parameter_grid.{key} must not be empty.")
        for value in values:
            if float(value) <= 0:
                errors.append(f"parameter_grid.{key} values must be positive.")
            if key.endswith("window") and not float(value).is_integer():
                errors.append(f"parameter_grid.{key} values must be integers.")


def _validate_momentum_grid_order(parameter_grid: dict[str, list[int | float]], errors: list[str]) -> None:
    fast_values = parameter_grid.get("fast_window")
    slow_values = parameter_grid.get("slow_window")
    if fast_values is None or slow_values is None:
        return
    if any(float(fast) >= float(slow) for fast in fast_values for slow in slow_values):
        errors.append("parameter_grid fast_window values must be less than slow_window values.")
