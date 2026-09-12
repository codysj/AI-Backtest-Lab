"""Base interfaces for bar-by-bar trading strategies."""

from abc import ABC, abstractmethod
from enum import Enum

import pandas as pd


class Signal(Enum):
    """Trading action emitted for the current bar."""

    BUY = 1
    SELL = -1
    HOLD = 0


class Strategy(ABC):
    """Abstract interface for one-bar-at-a-time strategy decisions.

    ``data`` is a bounded OHLCV history ending at ``current_index``. The engine
    intentionally prevents decision code from reaching later bars. A future
    read-only market-view abstraction may replace the bounded DataFrame without
    relaxing this causal contract.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""
        ...

    def precompute(self, data: pd.DataFrame) -> None:
        """Precompute any indicators needed during the hot backtest loop."""

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
        """Return exactly one signal for ``current_index``.

        ``data`` contains only values at indices ``<= current_index``.
        """
        ...


class MultiAssetStrategy(ABC):
    """Abstract interface for strategies that emit signals for many tickers.

    ``data`` maps ticker symbols to aligned OHLCV histories bounded at the
    current shared bar. ``current_index`` marks that final available row.
    Missing tickers in the returned mapping are treated as HOLD by the engine.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""
        ...

    def precompute(self, data: dict[str, pd.DataFrame]) -> None:
        """Precompute any indicators needed for all ticker DataFrames."""

    @abstractmethod
    def generate_signals(
        self,
        data: dict[str, pd.DataFrame],
        current_index: int,
    ) -> dict[str, Signal]:
        """Return ticker-to-signal mapping for ``current_index``."""
        ...
