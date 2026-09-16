"""Configuration for backtest execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PositionSizeMethod(Enum):
    """Available methods for translating BUY signals into order quantities."""

    FIXED_QUANTITY = "FIXED_QUANTITY"
    FIXED_DOLLAR = "FIXED_DOLLAR"
    ALL_IN = "ALL_IN"
    PERCENT_EQUITY = "PERCENT_EQUITY"
    VOLATILITY_TARGET = "VOLATILITY_TARGET"


class ExecutionPolicy(Enum):
    """Timing policy used to turn close-derived decisions into fills."""

    CLOSE_SIGNAL_NEXT_OPEN = "CLOSE_SIGNAL_NEXT_OPEN"
    SAME_CLOSE = "SAME_CLOSE"


@dataclass(frozen=True)
class BacktestConfig:
    """Immutable configuration for a single backtest run."""

    ticker: str
    start_date: str
    end_date: str
    initial_cash: float = 100_000.0
    commission_rate: float = 0.001
    slippage_bps: float = 5.0
    position_size_method: PositionSizeMethod = PositionSizeMethod.PERCENT_EQUITY
    position_size_value: float = 0.95
    volatility_window: int = 20
    execution_policy: ExecutionPolicy = ExecutionPolicy.CLOSE_SIGNAL_NEXT_OPEN
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_stop_pct: float | None = None

    def __post_init__(self) -> None:
        normalized_ticker = self.ticker.strip().upper()
        object.__setattr__(self, "ticker", normalized_ticker)
        if not normalized_ticker:
            msg = "ticker must be non-empty."
            raise ValueError(msg)
        if self.initial_cash <= 0:
            msg = "initial_cash must be positive."
            raise ValueError(msg)
        if self.commission_rate < 0:
            msg = "commission_rate must be non-negative."
            raise ValueError(msg)
        if self.slippage_bps < 0:
            msg = "slippage_bps must be non-negative."
            raise ValueError(msg)
        if self.position_size_value <= 0:
            msg = "position_size_value must be positive."
            raise ValueError(msg)
        if self.position_size_method in {
            PositionSizeMethod.PERCENT_EQUITY,
            PositionSizeMethod.VOLATILITY_TARGET,
        } and self.position_size_value > 1:
            msg = "position_size_value must be <= 1 for percent/risk sizing methods."
            raise ValueError(msg)
        if self.volatility_window <= 1:
            msg = "volatility_window must be greater than 1."
            raise ValueError(msg)
        _validate_risk_exits(self.stop_loss_pct, self.take_profit_pct, self.trailing_stop_pct)


@dataclass(frozen=True)
class MultiAssetBacktestConfig:
    """Immutable configuration for a multi-asset backtest run."""

    tickers: list[str]
    start_date: str
    end_date: str
    initial_cash: float = 100_000.0
    commission_rate: float = 0.001
    slippage_bps: float = 5.0
    position_size_method: PositionSizeMethod = PositionSizeMethod.PERCENT_EQUITY
    position_size_value: float = 0.95
    volatility_window: int = 20
    execution_policy: ExecutionPolicy = ExecutionPolicy.CLOSE_SIGNAL_NEXT_OPEN
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_stop_pct: float | None = None

    def __post_init__(self) -> None:
        normalized_tickers = [ticker.strip().upper() for ticker in self.tickers]
        if not normalized_tickers:
            msg = "tickers must be non-empty."
            raise ValueError(msg)
        if any(not ticker for ticker in normalized_tickers):
            msg = "ticker strings must be non-empty."
            raise ValueError(msg)
        object.__setattr__(self, "tickers", normalized_tickers)
        if self.initial_cash <= 0:
            msg = "initial_cash must be positive."
            raise ValueError(msg)
        if self.commission_rate < 0:
            msg = "commission_rate must be non-negative."
            raise ValueError(msg)
        if self.slippage_bps < 0:
            msg = "slippage_bps must be non-negative."
            raise ValueError(msg)
        if self.position_size_value <= 0:
            msg = "position_size_value must be positive."
            raise ValueError(msg)
        if self.position_size_method in {
            PositionSizeMethod.PERCENT_EQUITY,
            PositionSizeMethod.VOLATILITY_TARGET,
        } and self.position_size_value > 1:
            msg = "position_size_value must be <= 1 for percent/risk sizing methods."
            raise ValueError(msg)
        if self.volatility_window <= 1:
            msg = "volatility_window must be greater than 1."
            raise ValueError(msg)
        _validate_risk_exits(self.stop_loss_pct, self.take_profit_pct, self.trailing_stop_pct)


def _validate_risk_exits(*values: float | None) -> None:
    if any(value is not None and not 0 < value < 1 for value in values):
        msg = "stop_loss_pct, take_profit_pct, and trailing_stop_pct must be between 0 and 1."
        raise ValueError(msg)
