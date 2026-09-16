"""Constrained rule-based strategy implementation."""

from __future__ import annotations

import math
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray
import pandas as pd

from backtester.strategy import indicators
from backtester.strategy.base import Signal, Strategy
from backtester.strategy.rule_schema import (
    ConditionOperator,
    ConditionSpec,
    IndicatorName,
    IndicatorSpec,
    RuleBasedStrategySpec,
)


IndicatorKey: TypeAlias = tuple[IndicatorName, int | None, float | None, float | None]


class RuleBasedStrategy(Strategy):
    """Evaluate a strict, non-executable strategy rule specification."""

    def __init__(self, spec: RuleBasedStrategySpec) -> None:
        self._spec = spec
        self._indicators: dict[IndicatorKey, NDArray[np.float64]] = {}
        self._precomputed_length: int | None = None

    @property
    def name(self) -> str:
        return "RuleBasedStrategy"

    @property
    def spec(self) -> RuleBasedStrategySpec:
        """Return the validated rule spec used by the strategy."""
        return self._spec

    def precompute(self, data: pd.DataFrame) -> None:
        """Precompute only the indicators referenced by the rule spec."""
        self._indicators = {
            _indicator_key(indicator): _compute_indicator(indicator, data)
            for indicator in self._referenced_indicators()
        }
        self._precomputed_length = len(data)

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
        if current_index < 0 or current_index >= len(data):
            return Signal.HOLD
        if self._precomputed_length != len(data) or not self._indicators:
            self.precompute(data)

        if all(self._condition_is_true(condition, current_index) for condition in self._spec.rules.entry):
            return Signal.BUY
        if any(self._condition_is_true(condition, current_index) for condition in self._spec.rules.exit):
            return Signal.SELL
        return Signal.HOLD

    def _condition_is_true(self, condition: ConditionSpec, current_index: int) -> bool:
        left = self._value(condition.left, current_index)
        right = self._value(condition.right, current_index)
        if _is_missing(left) or _is_missing(right):
            return False

        operator = condition.operator
        if operator == ConditionOperator.GT:
            return left > right
        if operator == ConditionOperator.LT:
            return left < right
        if operator == ConditionOperator.GTE:
            return left >= right
        if operator == ConditionOperator.LTE:
            return left <= right

        if current_index == 0:
            return False
        left_previous = self._value(condition.left, current_index - 1)
        right_previous = self._value(condition.right, current_index - 1)
        if _is_missing(left_previous) or _is_missing(right_previous):
            return False
        if operator == ConditionOperator.CROSSES_ABOVE:
            return left_previous <= right_previous and left > right
        if operator == ConditionOperator.CROSSES_BELOW:
            return left_previous >= right_previous and left < right
        return False

    def _value(self, indicator: IndicatorSpec, current_index: int) -> float:
        values = self._indicators.get(_indicator_key(indicator))
        if values is None:
            return float("nan")
        return float(values[current_index])

    def _referenced_indicators(self) -> list[IndicatorSpec]:
        indicators: list[IndicatorSpec] = []
        seen: set[IndicatorKey] = set()
        for condition in [*self._spec.rules.entry, *self._spec.rules.exit]:
            for indicator in [condition.left, condition.right]:
                key = _indicator_key(indicator)
                if key not in seen:
                    indicators.append(indicator)
                    seen.add(key)
        return indicators


def _compute_indicator(indicator: IndicatorSpec, data: pd.DataFrame) -> NDArray[np.float64]:
    close = data["close"]
    if indicator.name == IndicatorName.CLOSE:
        return close.to_numpy(dtype=float)
    if indicator.name == IndicatorName.VALUE:
        return np.full(len(data), float(indicator.value if indicator.value is not None else "nan"))

    window = _required_window(indicator)
    if indicator.name == IndicatorName.SMA:
        return indicators.sma(close, window).to_numpy(dtype=float)
    if indicator.name == IndicatorName.EMA:
        return indicators.ema(close, window).to_numpy(dtype=float)
    if indicator.name == IndicatorName.RSI:
        return indicators.rsi(close, window).to_numpy(dtype=float)
    if indicator.name == IndicatorName.ROLLING_HIGH:
        return indicators.prior_high(data["high"], window).to_numpy(dtype=float)
    if indicator.name == IndicatorName.ROLLING_LOW:
        return indicators.prior_low(data["low"], window).to_numpy(dtype=float)

    rolling_mean = close.rolling(window).mean()
    rolling_std = close.rolling(window).std()
    num_std = _required_num_std(indicator)
    if indicator.name == IndicatorName.BOLLINGER_UPPER:
        return (rolling_mean + num_std * rolling_std).to_numpy(dtype=float)
    if indicator.name == IndicatorName.BOLLINGER_LOWER:
        return (rolling_mean - num_std * rolling_std).to_numpy(dtype=float)

    msg = f"Unsupported indicator: {indicator.name.value}."
    raise ValueError(msg)


def _indicator_key(indicator: IndicatorSpec) -> IndicatorKey:
    return (indicator.name, indicator.window, indicator.num_std, indicator.value)


def _required_window(indicator: IndicatorSpec) -> int:
    if indicator.window is None:
        msg = f"{indicator.name.value} requires window."
        raise ValueError(msg)
    return indicator.window


def _required_num_std(indicator: IndicatorSpec) -> float:
    if indicator.num_std is None:
        msg = f"{indicator.name.value} requires num_std."
        raise ValueError(msg)
    return indicator.num_std


def _is_missing(value: float) -> bool:
    return math.isnan(value) or not math.isfinite(value)
