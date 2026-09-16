"""Strict schemas for constrained rule-based strategy definitions."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IndicatorName(str, Enum):
    """Indicators supported by the v1 rule DSL."""

    CLOSE = "close"
    SMA = "sma"
    ROLLING_HIGH = "rolling_high"
    ROLLING_LOW = "rolling_low"
    BOLLINGER_UPPER = "bollinger_upper"
    BOLLINGER_LOWER = "bollinger_lower"
    EMA = "ema"
    RSI = "rsi"
    VALUE = "value"


class ConditionOperator(str, Enum):
    """Comparison operators supported by the v1 rule DSL."""

    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"


class IndicatorSpec(BaseModel):
    """One constrained indicator reference.

    ``rolling_high`` and ``rolling_low`` are evaluated over completed prior
    bars so breakout rules do not compare today's close with today's high/low.
    ``value`` is a constant operand, for example ``rsi(14) < value(30)``.
    """

    model_config = ConfigDict(extra="forbid")

    name: IndicatorName
    window: int | None = Field(default=None, gt=0)
    num_std: float | None = Field(default=None, gt=0)
    value: float | None = None

    @model_validator(mode="after")
    def validate_indicator_parameters(self) -> "IndicatorSpec":
        if self.name == IndicatorName.VALUE:
            if self.value is None or self.window is not None or self.num_std is not None:
                msg = "value requires value and does not accept window or num_std."
                raise ValueError(msg)
            return self
        if self.value is not None:
            msg = f"{self.name.value} does not accept value."
            raise ValueError(msg)

        if self.name == IndicatorName.CLOSE:
            if self.window is not None or self.num_std is not None:
                msg = "close does not accept window or num_std."
                raise ValueError(msg)
            return self

        if self.name in {
            IndicatorName.SMA,
            IndicatorName.EMA,
            IndicatorName.RSI,
            IndicatorName.ROLLING_HIGH,
            IndicatorName.ROLLING_LOW,
        }:
            if self.window is None:
                msg = f"{self.name.value} requires window."
                raise ValueError(msg)
            if self.num_std is not None:
                msg = f"{self.name.value} does not accept num_std."
                raise ValueError(msg)
            return self

        if self.name in {IndicatorName.BOLLINGER_UPPER, IndicatorName.BOLLINGER_LOWER}:
            if self.window is None:
                msg = f"{self.name.value} requires window."
                raise ValueError(msg)
            if self.num_std is None:
                msg = f"{self.name.value} requires num_std."
                raise ValueError(msg)
            return self

        msg = f"Unsupported indicator: {self.name.value}."
        raise ValueError(msg)


class ConditionSpec(BaseModel):
    """One constrained rule condition."""

    model_config = ConfigDict(extra="forbid")

    left: IndicatorSpec
    operator: ConditionOperator
    right: IndicatorSpec


class RuleSetSpec(BaseModel):
    """Entry and exit rules for a constrained rule-based strategy.

    V1 uses AND for entry conditions and ANY for exit conditions.
    """

    model_config = ConfigDict(extra="forbid")

    entry: list[ConditionSpec] = Field(..., min_length=1, max_length=4)
    exit: list[ConditionSpec] = Field(..., min_length=1, max_length=4)


class RuleBasedStrategySpec(BaseModel):
    """Top-level v1 rule-based strategy specification."""

    model_config = ConfigDict(extra="forbid")

    rules: RuleSetSpec
