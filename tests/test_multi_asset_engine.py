from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from backtester.data.loader import DataLoader
from backtester.engine import MultiAssetBacktestConfig, MultiAssetBacktestEngine, PositionSizeMethod
from backtester.strategy import MomentumStrategy, MultiAssetStrategy, Signal, SingleStrategyMultiAssetWrapper


def make_ohlcv(closes: list[float], start: str = "2020-01-01") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [100] * len(closes),
        },
        index=pd.date_range(start, periods=len(closes), freq="D", name="date"),
    )


@dataclass
class FakeMultiLoader(DataLoader):
    data: dict[str, pd.DataFrame]

    def fetch(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        del start, end
        return self.data[ticker].copy()


class MultiHoldStrategy(MultiAssetStrategy):
    @property
    def name(self) -> str:
        return "MultiHold"

    def generate_signals(self, data: dict[str, pd.DataFrame], current_index: int) -> dict[str, Signal]:
        del data, current_index
        return {}


class BuyFirstMultiStrategy(MultiAssetStrategy):
    @property
    def name(self) -> str:
        return "BuyFirst"

    def generate_signals(self, data: dict[str, pd.DataFrame], current_index: int) -> dict[str, Signal]:
        if current_index == 0:
            return {ticker: Signal.BUY for ticker in data}
        return {ticker: Signal.HOLD for ticker in data}


class BuyThenSellOneTickerStrategy(MultiAssetStrategy):
    @property
    def name(self) -> str:
        return "BuyThenSellOne"

    def generate_signals(self, data: dict[str, pd.DataFrame], current_index: int) -> dict[str, Signal]:
        del data
        if current_index == 0:
            return {"AAA": Signal.BUY, "BBB": Signal.BUY}
        if current_index == 1:
            return {"AAA": Signal.SELL}
        return {}


def make_config() -> MultiAssetBacktestConfig:
    return MultiAssetBacktestConfig(
        tickers=["AAA", "BBB"],
        start_date="2020-01-01",
        end_date="2020-01-05",
        initial_cash=10_000.0,
        commission_rate=0.0,
        slippage_bps=0.0,
        position_size_method=PositionSizeMethod.FIXED_QUANTITY,
        position_size_value=10.0,
    )


def test_multi_asset_no_trade_strategy_equity_flat() -> None:
    loader = FakeMultiLoader({"AAA": make_ohlcv([100.0, 101.0]), "BBB": make_ohlcv([50.0, 52.0])})
    result = MultiAssetBacktestEngine(loader, MultiHoldStrategy(), make_config()).run()

    assert list(result.equity_curve) == [10_000.0, 10_000.0]
    assert result.trades == []


def test_multi_asset_buy_first_buys_multiple_tickers_if_cash_allows() -> None:
    loader = FakeMultiLoader({"AAA": make_ohlcv([100.0, 100.0]), "BBB": make_ohlcv([50.0, 50.0])})
    result = MultiAssetBacktestEngine(loader, BuyFirstMultiStrategy(), make_config()).run()

    assert [trade.ticker for trade in result.trades] == ["AAA", "BBB"]
    assert [trade.quantity for trade in result.trades] == [10, 10]


def test_multi_asset_equity_curve_uses_common_aligned_dates() -> None:
    loader = FakeMultiLoader(
        {
            "AAA": make_ohlcv([100.0, 101.0, 102.0], "2020-01-01"),
            "BBB": make_ohlcv([50.0, 51.0, 52.0], "2020-01-02"),
        }
    )
    result = MultiAssetBacktestEngine(loader, MultiHoldStrategy(), make_config()).run()

    assert len(result.equity_curve) == 2
    assert list(result.price_data["AAA"].index) == list(result.price_data["BBB"].index)


def test_multi_asset_sell_liquidates_only_that_ticker() -> None:
    loader = FakeMultiLoader({"AAA": make_ohlcv([100.0, 110.0, 110.0]), "BBB": make_ohlcv([50.0, 60.0, 60.0])})
    result = MultiAssetBacktestEngine(loader, BuyThenSellOneTickerStrategy(), make_config()).run()

    assert [trade.ticker for trade in result.trades] == ["AAA", "BBB", "AAA"]
    assert result.trades[-1].side.value == "SELL"
    assert result.final_value == pytest.approx(10_000.0)


def test_wrapper_applies_single_asset_strategy_independently() -> None:
    data = {
        "AAA": make_ohlcv([5.0, 5.0, 5.0, 8.0]),
        "BBB": make_ohlcv([5.0, 5.0, 5.0, 2.0]),
    }
    wrapper = SingleStrategyMultiAssetWrapper(lambda: MomentumStrategy(fast_window=2, slow_window=3))

    wrapper.precompute(data)
    signals = wrapper.generate_signals(data, current_index=3)

    assert signals == {"AAA": Signal.BUY, "BBB": Signal.SELL}
