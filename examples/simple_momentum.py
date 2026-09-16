"""Minimal synthetic MomentumStrategy example."""

from __future__ import annotations

import math
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtester.data.loader import DataLoader
from backtester.engine import BacktestConfig, BacktestEngine, PositionSizeMethod
from backtester.metrics import generate_report, print_report
from backtester.strategy import MomentumStrategy


class SyntheticLoader(DataLoader):
    def fetch(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        del ticker, start, end
        dates = pd.date_range("2020-01-01", periods=120, freq="B", name="date")
        # A slow wave on a mild trend, so the 10/30 SMAs actually cross.
        closes = [100.0 + index * 0.05 + 8.0 * math.sin(index / 9) for index in range(120)]
        return pd.DataFrame(
            {
                "open": closes,
                "high": [close * 1.01 for close in closes],
                "low": [close * 0.99 for close in closes],
                "close": closes,
                "volume": [100_000] * len(closes),
            },
            index=dates,
        )


def main() -> None:
    config = BacktestConfig(
        ticker="SYNTH",
        start_date="2020-01-01",
        end_date="2020-06-30",
        position_size_method=PositionSizeMethod.FIXED_DOLLAR,
        position_size_value=10_000.0,
    )
    strategy = MomentumStrategy(fast_window=10, slow_window=30)
    result = BacktestEngine(loader=SyntheticLoader(), strategy=strategy, config=config).run()

    print(f"strategy: {result.strategy_name}")
    print(f"initial_value: {result.initial_value:.2f}")
    print(f"final_value: {result.final_value:.2f}")
    print(f"trade_count: {len(result.trades)}")
    print_report(generate_report(result))


if __name__ == "__main__":
    main()

