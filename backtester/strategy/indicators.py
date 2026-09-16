"""Causal technical indicators shared by built-in strategies and the rule DSL.

Every function returns a Series aligned to the input index where row ``i``
depends only on rows ``<= i``.
"""

from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average seeded from the first observation."""
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(close: pd.Series, window: int) -> pd.Series:
    """Wilder's Relative Strength Index on a 0-100 scale."""
    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    alpha = 1.0 / window
    avg_gain = gains.ewm(alpha=alpha, adjust=False, min_periods=window).mean()
    avg_loss = losses.ewm(alpha=alpha, adjust=False, min_periods=window).mean()
    # A window with no losses is maximally overbought; no movement at all is neutral.
    rs = avg_gain / avg_loss
    values = 100.0 - 100.0 / (1.0 + rs)
    values = values.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    return values.mask((avg_loss == 0) & (avg_gain == 0), 50.0)


def macd(close: pd.Series, fast: int, slow: int, signal: int) -> tuple[pd.Series, pd.Series]:
    """Return the MACD line and its signal line."""
    line = ema(close, fast) - ema(close, slow)
    return line, line.ewm(span=signal, adjust=False, min_periods=signal).mean()


def prior_high(high: pd.Series, window: int) -> pd.Series:
    """Highest high over the ``window`` completed bars before the current bar."""
    return high.rolling(window).max().shift(1)


def prior_low(low: pd.Series, window: int) -> pd.Series:
    """Lowest low over the ``window`` completed bars before the current bar."""
    return low.rolling(window).min().shift(1)
