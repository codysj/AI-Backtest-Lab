from __future__ import annotations

import pandas as pd
import pytest
from pydantic import ValidationError

from backtester.strategy import (
    ConditionOperator,
    ConditionSpec,
    IndicatorName,
    IndicatorSpec,
    RuleBasedStrategy,
    RuleBasedStrategySpec,
    RuleSetSpec,
    Signal,
)


def ohlcv_from_closes(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [100] * len(closes),
        },
        index=pd.date_range("2020-01-01", periods=len(closes), name="date"),
    )


def close() -> IndicatorSpec:
    return IndicatorSpec(name=IndicatorName.CLOSE)


def sma(window: int) -> IndicatorSpec:
    return IndicatorSpec(name=IndicatorName.SMA, window=window)


def rolling_high(window: int) -> IndicatorSpec:
    return IndicatorSpec(name=IndicatorName.ROLLING_HIGH, window=window)


def rolling_low(window: int) -> IndicatorSpec:
    return IndicatorSpec(name=IndicatorName.ROLLING_LOW, window=window)


def bollinger_upper(window: int, num_std: float) -> IndicatorSpec:
    return IndicatorSpec(name=IndicatorName.BOLLINGER_UPPER, window=window, num_std=num_std)


def bollinger_lower(window: int, num_std: float) -> IndicatorSpec:
    return IndicatorSpec(name=IndicatorName.BOLLINGER_LOWER, window=window, num_std=num_std)


def condition(
    left: IndicatorSpec,
    operator: ConditionOperator,
    right: IndicatorSpec,
) -> ConditionSpec:
    return ConditionSpec(left=left, operator=operator, right=right)


def spec(entry: ConditionSpec, exit_condition: ConditionSpec) -> RuleBasedStrategySpec:
    return RuleBasedStrategySpec(rules=RuleSetSpec(entry=[entry], exit=[exit_condition]))


def latest_signal(strategy: RuleBasedStrategy, data: pd.DataFrame) -> Signal:
    return strategy.generate_signal(data, current_index=len(data) - 1)


def test_close_crosses_above_sma_triggers_buy_at_expected_bar() -> None:
    strategy = RuleBasedStrategy(
        spec(
            condition(close(), ConditionOperator.CROSSES_ABOVE, sma(3)),
            condition(close(), ConditionOperator.CROSSES_BELOW, sma(3)),
        )
    )

    assert latest_signal(strategy, ohlcv_from_closes([10.0, 10.0, 10.0, 13.0])) is Signal.BUY


def test_close_crosses_below_sma_triggers_sell_at_expected_bar() -> None:
    strategy = RuleBasedStrategy(
        spec(
            condition(close(), ConditionOperator.CROSSES_ABOVE, sma(3)),
            condition(close(), ConditionOperator.CROSSES_BELOW, sma(3)),
        )
    )

    assert latest_signal(strategy, ohlcv_from_closes([10.0, 10.0, 10.0, 7.0])) is Signal.SELL


def test_rolling_high_breakout_triggers_buy() -> None:
    strategy = RuleBasedStrategy(
        spec(
            condition(close(), ConditionOperator.GT, rolling_high(3)),
            condition(close(), ConditionOperator.LT, rolling_low(3)),
        )
    )

    assert latest_signal(strategy, ohlcv_from_closes([10.0, 11.0, 12.0, 13.0])) is Signal.BUY


def test_bollinger_lower_band_condition_triggers_buy() -> None:
    strategy = RuleBasedStrategy(
        spec(
            condition(close(), ConditionOperator.LTE, bollinger_lower(3, 1.0)),
            condition(close(), ConditionOperator.GTE, bollinger_upper(3, 1.0)),
        )
    )

    assert latest_signal(strategy, ohlcv_from_closes([10.0, 10.0, 0.0])) is Signal.BUY


def test_rule_based_warmup_period_returns_hold() -> None:
    strategy = RuleBasedStrategy(
        spec(
            condition(close(), ConditionOperator.CROSSES_ABOVE, sma(3)),
            condition(close(), ConditionOperator.CROSSES_BELOW, sma(3)),
        )
    )

    assert latest_signal(strategy, ohlcv_from_closes([10.0, 10.0, 10.0])) is Signal.HOLD


def test_rule_based_strategy_does_not_look_ahead() -> None:
    rule_spec = spec(
        condition(close(), ConditionOperator.GT, rolling_high(3)),
        condition(close(), ConditionOperator.LT, rolling_low(3)),
    )
    full_data = ohlcv_from_closes([10.0, 11.0, 12.0, 11.0, 100.0])
    truncated_data = full_data.iloc[:4].copy()
    full_strategy = RuleBasedStrategy(rule_spec)
    truncated_strategy = RuleBasedStrategy(rule_spec)

    full_strategy.precompute(full_data)
    truncated_strategy.precompute(truncated_data)

    assert full_strategy.generate_signal(full_data, current_index=3) is Signal.HOLD
    assert truncated_strategy.generate_signal(truncated_data, current_index=3) is Signal.HOLD


def test_invalid_indicator_operator_and_window_are_rejected() -> None:
    with pytest.raises(ValidationError):
        IndicatorSpec.model_validate({"name": "vwap", "window": 10})

    with pytest.raises(ValidationError):
        ConditionSpec.model_validate(
            {
                "left": {"name": "close"},
                "operator": "contains",
                "right": {"name": "sma", "window": 10},
            }
        )

    with pytest.raises(ValidationError):
        IndicatorSpec.model_validate({"name": "sma", "window": 0})

    with pytest.raises(ValidationError):
        IndicatorSpec.model_validate({"name": "close", "window": 10})
