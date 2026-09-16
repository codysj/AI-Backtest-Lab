"""Single source of truth for built-in, parameterized strategies.

The API, CLI, AI compiler, and research workflows all read strategy ids,
parameter metadata, defaults, and default research grids from here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from backtester.strategy.base import Strategy
from backtester.strategy.mean_reversion import MeanReversionStrategy
from backtester.strategy.momentum import MomentumStrategy
from backtester.strategy.oscillators import DonchianBreakoutStrategy, MacdCrossoverStrategy, RsiReversionStrategy


@dataclass(frozen=True)
class ParameterSpec:
    """One numeric strategy parameter."""

    name: str
    type: Literal["integer", "number"]
    default: int | float
    min: int | float
    label: str
    grid: tuple[int | float, ...]


@dataclass(frozen=True)
class StrategySpec:
    """Metadata and factory for one built-in strategy."""

    id: str
    name: str
    description: str
    factory: Callable[..., Strategy]
    parameters: tuple[ParameterSpec, ...]

    @property
    def parameter_names(self) -> set[str]:
        return {parameter.name for parameter in self.parameters}

    def default_grid(self) -> dict[str, list[int | float]]:
        return {parameter.name: list(parameter.grid) for parameter in self.parameters}

    def build(self, parameters: Mapping[str, int | float]) -> Strategy:
        """Coerce parameters, fill defaults, and construct the strategy.

        Raises ValueError for unknown parameters or values the strategy rejects.
        """
        unexpected = set(parameters) - self.parameter_names
        if unexpected:
            msg = f"Unsupported parameter(s) for {self.id}: {', '.join(sorted(unexpected))}."
            raise ValueError(msg)
        kwargs: dict[str, int | float] = {}
        for parameter in self.parameters:
            value = parameters.get(parameter.name, parameter.default)
            if parameter.type == "integer":
                if float(value) != int(value):
                    msg = f"{parameter.name} must be an integer."
                    raise ValueError(msg)
                kwargs[parameter.name] = int(value)
            else:
                kwargs[parameter.name] = float(value)
        return self.factory(**kwargs)


STRATEGIES: dict[str, StrategySpec] = {
    spec.id: spec
    for spec in (
        StrategySpec(
            id="momentum",
            name="Momentum SMA Crossover",
            description="Buys when the fast SMA crosses above the slow SMA and sells on the reverse cross.",
            factory=MomentumStrategy,
            parameters=(
                ParameterSpec("fast_window", "integer", 10, 1, "Fast Window", (5, 10, 20)),
                ParameterSpec("slow_window", "integer", 50, 2, "Slow Window", (50, 100, 200)),
            ),
        ),
        StrategySpec(
            id="mean_reversion",
            name="Bollinger Mean Reversion",
            description="Buys at or below the lower Bollinger band and sells at or above the upper band.",
            factory=MeanReversionStrategy,
            parameters=(
                ParameterSpec("window", "integer", 20, 2, "Window", (10, 20, 30)),
                ParameterSpec("num_std", "number", 2.0, 0.1, "Standard Deviations", (1.5, 2.0, 2.5)),
            ),
        ),
        StrategySpec(
            id="rsi_reversion",
            name="RSI Reversion",
            description="Buys when Wilder RSI crosses down into oversold and sells once RSI is overbought.",
            factory=RsiReversionStrategy,
            parameters=(
                ParameterSpec("window", "integer", 14, 2, "RSI Window", (7, 14, 21)),
                ParameterSpec("oversold", "number", 30.0, 1, "Oversold", (20.0, 30.0)),
                ParameterSpec("overbought", "number", 70.0, 1, "Overbought", (70.0, 80.0)),
            ),
        ),
        StrategySpec(
            id="donchian_breakout",
            name="Donchian Breakout",
            description="Buys when close breaks the prior N-bar high and sells when it breaks the prior M-bar low.",
            factory=DonchianBreakoutStrategy,
            parameters=(
                ParameterSpec("entry_window", "integer", 20, 1, "Entry Window", (20, 55)),
                ParameterSpec("exit_window", "integer", 10, 1, "Exit Window", (10, 20)),
            ),
        ),
        StrategySpec(
            id="macd_crossover",
            name="MACD Crossover",
            description="Buys when the MACD line crosses above its signal line and sells on the reverse cross.",
            factory=MacdCrossoverStrategy,
            parameters=(
                ParameterSpec("fast_span", "integer", 12, 1, "Fast Span", (8, 12)),
                ParameterSpec("slow_span", "integer", 26, 2, "Slow Span", (21, 26)),
                ParameterSpec("signal_span", "integer", 9, 1, "Signal Span", (5, 9)),
            ),
        ),
    )
}
