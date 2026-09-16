"""RSI, Donchian breakout, and MACD built-in strategies."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray
import pandas as pd

from backtester.strategy import indicators
from backtester.strategy.base import Signal, Strategy


def _crossed_above(left: NDArray[np.float64], right: NDArray[np.float64], i: int) -> bool:
    if i < 1:
        return False
    values = (left[i - 1], right[i - 1], left[i], right[i])
    if any(math.isnan(float(value)) for value in values):
        return False
    return bool(left[i - 1] <= right[i - 1] and left[i] > right[i])


def _crossed_below(left: NDArray[np.float64], right: NDArray[np.float64], i: int) -> bool:
    return _crossed_above(right, left, i)


class RsiReversionStrategy(Strategy):
    """Buy when RSI drops into oversold territory; sell once it is overbought."""

    def __init__(self, window: int = 14, oversold: float = 30.0, overbought: float = 70.0) -> None:
        if window <= 1:
            msg = "window must be greater than 1."
            raise ValueError(msg)
        if not 0 < oversold < overbought < 100:
            msg = "RSI thresholds must satisfy 0 < oversold < overbought < 100."
            raise ValueError(msg)
        self._window = window
        self._oversold = oversold
        self._overbought = overbought
        self._rsi: NDArray[np.float64] = np.array([], dtype=float)

    @property
    def name(self) -> str:
        return f"RSI({self._window}, {self._oversold:g}/{self._overbought:g})"

    def precompute(self, data: pd.DataFrame) -> None:
        self._rsi = indicators.rsi(data["close"], self._window).to_numpy(dtype=float)

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
        if len(self._rsi) != len(data):
            self.precompute(data)
        now = float(self._rsi[current_index])
        previous = float(self._rsi[current_index - 1]) if current_index > 0 else float("nan")
        if math.isnan(now):
            return Signal.HOLD
        if not math.isnan(previous) and previous >= self._oversold > now:
            return Signal.BUY
        if now >= self._overbought:
            return Signal.SELL
        return Signal.HOLD


class DonchianBreakoutStrategy(Strategy):
    """Turtle-style channel breakout: enter on a new N-bar high, exit on an M-bar low."""

    def __init__(self, entry_window: int = 20, exit_window: int = 10) -> None:
        if entry_window <= 0 or exit_window <= 0:
            msg = "entry_window and exit_window must be positive."
            raise ValueError(msg)
        self._entry_window = entry_window
        self._exit_window = exit_window
        self._close: NDArray[np.float64] = np.array([], dtype=float)
        self._upper: NDArray[np.float64] = np.array([], dtype=float)
        self._lower: NDArray[np.float64] = np.array([], dtype=float)

    @property
    def name(self) -> str:
        return f"Donchian({self._entry_window}/{self._exit_window})"

    def precompute(self, data: pd.DataFrame) -> None:
        self._close = data["close"].to_numpy(dtype=float)
        self._upper = indicators.prior_high(data["high"], self._entry_window).to_numpy(dtype=float)
        self._lower = indicators.prior_low(data["low"], self._exit_window).to_numpy(dtype=float)

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
        if len(self._close) != len(data):
            self.precompute(data)
        if _crossed_above(self._close, self._upper, current_index):
            return Signal.BUY
        lower = float(self._lower[current_index])
        if not math.isnan(lower) and self._close[current_index] < lower:
            return Signal.SELL
        return Signal.HOLD


class MacdCrossoverStrategy(Strategy):
    """Trade crossovers of the MACD line through its signal line."""

    def __init__(self, fast_span: int = 12, slow_span: int = 26, signal_span: int = 9) -> None:
        if fast_span <= 0 or slow_span <= 0 or signal_span <= 0:
            msg = "MACD spans must be positive."
            raise ValueError(msg)
        if fast_span >= slow_span:
            msg = "fast_span must be less than slow_span."
            raise ValueError(msg)
        self._fast = fast_span
        self._slow = slow_span
        self._signal = signal_span
        self._line: NDArray[np.float64] = np.array([], dtype=float)
        self._signal_line: NDArray[np.float64] = np.array([], dtype=float)

    @property
    def name(self) -> str:
        return f"MACD({self._fast}/{self._slow}/{self._signal})"

    def precompute(self, data: pd.DataFrame) -> None:
        line, signal_line = indicators.macd(data["close"], self._fast, self._slow, self._signal)
        self._line = line.to_numpy(dtype=float)
        self._signal_line = signal_line.to_numpy(dtype=float)

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
        if len(self._line) != len(data):
            self.precompute(data)
        if _crossed_above(self._line, self._signal_line, current_index):
            return Signal.BUY
        if _crossed_below(self._line, self._signal_line, current_index):
            return Signal.SELL
        return Signal.HOLD
