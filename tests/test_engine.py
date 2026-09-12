from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from backtester.data.loader import DataLoader
from backtester.engine import BacktestConfig, BacktestEngine, ExecutionPolicy, PositionSizeMethod
from backtester.portfolio import OrderStatus
from backtester.strategy import Signal, Strategy


def make_ohlcv_df(close_prices: list[float], open_prices: list[float] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": open_prices if open_prices is not None else close_prices,
            "high": close_prices,
            "low": close_prices,
            "close": close_prices,
            "volume": [100] * len(close_prices),
        },
        index=pd.date_range("2020-01-01", periods=len(close_prices), name="date"),
    )


@dataclass
class FakeLoader(DataLoader):
    data: pd.DataFrame

    def fetch(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        return self.data.copy()


class AlwaysHoldStrategy(Strategy):
    @property
    def name(self) -> str:
        return "AlwaysHold"

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
        del data, current_index
        return Signal.HOLD


class BuyFirstBarStrategy(Strategy):
    @property
    def name(self) -> str:
        return "BuyFirstBar"

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
        del data
        if current_index == 0:
            return Signal.BUY
        return Signal.HOLD


class BuyThenSellStrategy(Strategy):
    @property
    def name(self) -> str:
        return "BuyThenSell"

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
        del data
        if current_index == 0:
            return Signal.BUY
        if current_index == 1:
            return Signal.SELL
        return Signal.HOLD


class RecordingIndexStrategy(Strategy):
    def __init__(self) -> None:
        self.indices: list[int] = []

    @property
    def name(self) -> str:
        return "RecordingIndex"

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
        assert len(data) == current_index + 1
        self.indices.append(current_index)
        return Signal.HOLD


def make_engine(
    data: pd.DataFrame,
    strategy: Strategy,
    config: BacktestConfig,
) -> BacktestEngine:
    return BacktestEngine(loader=FakeLoader(data), strategy=strategy, config=config)


def test_no_trade_strategy_equity_curve_flat() -> None:
    config = BacktestConfig("AAPL", "2020-01-01", "2020-01-04", initial_cash=1_000.0)
    result = make_engine(make_ohlcv_df([100.0, 105.0, 110.0]), AlwaysHoldStrategy(), config).run()

    assert len(result.equity_curve) == 3
    assert list(result.equity_curve) == [1_000.0, 1_000.0, 1_000.0]
    assert result.trades == []


def test_buy_and_hold_final_value_hand_calculation() -> None:
    config = BacktestConfig(
        "AAPL",
        "2020-01-01",
        "2020-01-04",
        initial_cash=1_000.0,
        commission_rate=0.001,
        slippage_bps=5.0,
        position_size_method=PositionSizeMethod.FIXED_QUANTITY,
        position_size_value=5.0,
    )

    result = make_engine(make_ohlcv_df([100.0, 110.0, 120.0]), BuyFirstBarStrategy(), config).run()

    expected_entry_price = 110.0 * 1.0005
    expected_cash = round(1_000.0 - (5 * expected_entry_price + 0.005), 2)
    expected_final_value = expected_cash + 5 * 120.0
    assert result.final_value == pytest.approx(expected_final_value)


def test_buy_then_sell_cash_only_after_sell() -> None:
    config = BacktestConfig(
        "AAPL",
        "2020-01-01",
        "2020-01-04",
        initial_cash=1_000.0,
        commission_rate=0.0,
        slippage_bps=0.0,
        position_size_method=PositionSizeMethod.FIXED_QUANTITY,
        position_size_value=5.0,
    )

    result = make_engine(make_ohlcv_df([100.0, 110.0, 120.0]), BuyThenSellStrategy(), config).run()

    assert len(result.trades) == 2
    assert result.trades[-1].side.value == "SELL"
    assert result.final_value == pytest.approx(1_050.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(1_050.0)


def test_lookahead_contract_records_incremental_indices() -> None:
    strategy = RecordingIndexStrategy()
    config = BacktestConfig("AAPL", "2020-01-01", "2020-01-05")

    make_engine(make_ohlcv_df([1.0, 2.0, 3.0, 4.0]), strategy, config).run()

    assert strategy.indices == [0, 1, 2, 3]


def test_close_signal_fills_at_next_available_open_with_linked_audit_events() -> None:
    data = make_ohlcv_df([100.0, 120.0, 130.0], [95.0, 110.0, 125.0])
    config = BacktestConfig(
        "AAPL",
        "2020-01-01",
        "2020-01-04",
        initial_cash=1_000.0,
        commission_rate=0.0,
        slippage_bps=0.0,
        position_size_method=PositionSizeMethod.FIXED_QUANTITY,
        position_size_value=2.0,
    )

    result = make_engine(data, BuyFirstBarStrategy(), config).run()

    assert result.orders[0].timestamp == data.index[0].to_pydatetime()
    assert result.fills[0].filled_at == data.index[1].to_pydatetime()
    assert result.fills[0].reference_price == 110.0
    assert result.trades[0].price == 110.0
    assert result.orders[0].decision_id == result.decisions[0].decision_id
    assert [event.status for event in result.order_events] == [OrderStatus.SUBMITTED, OrderStatus.FILLED]


def test_last_bar_order_expires_without_a_fill() -> None:
    class BuyLastBar(Strategy):
        @property
        def name(self) -> str:
            return "BuyLastBar"

        def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
            del data
            return Signal.BUY if current_index == 1 else Signal.HOLD

    result = make_engine(
        make_ohlcv_df([100.0, 101.0]),
        BuyLastBar(),
        BacktestConfig("AAPL", "2020-01-01", "2020-01-03"),
    ).run()

    assert result.trades == []
    assert result.fills == []
    assert result.order_events[-1].status is OrderStatus.EXPIRED


def test_future_bar_mutation_cannot_change_earlier_decisions() -> None:
    original = make_ohlcv_df([10.0, 11.0, 12.0, 13.0])
    mutated = original.copy()
    mutated.iloc[2:, mutated.columns.get_loc("close")] = [1_000.0, 0.01]
    config = BacktestConfig("AAPL", "2020-01-01", "2020-01-05")

    first = make_engine(original, BuyFirstBarStrategy(), config).run()
    second = make_engine(mutated, BuyFirstBarStrategy(), config).run()

    assert first.decisions[:2] == second.decisions[:2]
    assert first.orders[:1] == second.orders[:1]


def test_same_close_policy_is_explicit_opt_in() -> None:
    data = make_ohlcv_df([100.0, 120.0], [90.0, 110.0])
    config = BacktestConfig(
        "AAPL",
        "2020-01-01",
        "2020-01-03",
        commission_rate=0.0,
        slippage_bps=0.0,
        position_size_method=PositionSizeMethod.FIXED_QUANTITY,
        position_size_value=1.0,
        execution_policy=ExecutionPolicy.SAME_CLOSE,
    )

    result = make_engine(data, BuyFirstBarStrategy(), config).run()

    assert result.fills[0].reference_price == 100.0
    assert result.fills[0].filled_at == result.orders[0].timestamp


def test_equity_curve_length_matches_data_length() -> None:
    config = BacktestConfig("AAPL", "2020-01-01", "2020-01-05")

    result = make_engine(make_ohlcv_df([10.0, 11.0, 12.0, 13.0]), AlwaysHoldStrategy(), config).run()

    assert len(result.equity_curve) == 4


def test_fixed_quantity_position_sizing() -> None:
    config = BacktestConfig(
        "AAPL",
        "2020-01-01",
        "2020-01-03",
        position_size_method=PositionSizeMethod.FIXED_QUANTITY,
        position_size_value=7.0,
    )

    result = make_engine(make_ohlcv_df([100.0, 100.0]), BuyFirstBarStrategy(), config).run()

    assert result.trades[0].quantity == 7


def test_fixed_dollar_position_sizing() -> None:
    config = BacktestConfig(
        "AAPL",
        "2020-01-01",
        "2020-01-03",
        position_size_method=PositionSizeMethod.FIXED_DOLLAR,
        position_size_value=250.0,
    )

    result = make_engine(make_ohlcv_df([100.0, 100.0]), BuyFirstBarStrategy(), config).run()

    assert result.trades[0].quantity == 2


def test_all_in_position_sizing() -> None:
    config = BacktestConfig(
        "AAPL",
        "2020-01-01",
        "2020-01-03",
        initial_cash=1_000.0,
        commission_rate=0.0,
        slippage_bps=0.0,
        position_size_method=PositionSizeMethod.ALL_IN,
    )

    result = make_engine(make_ohlcv_df([100.0, 100.0]), BuyFirstBarStrategy(), config).run()

    assert result.trades[0].quantity == 10


def test_non_positive_price_buy_signal_does_not_create_trade() -> None:
    config = BacktestConfig(
        "AAPL",
        "2020-01-01",
        "2020-01-03",
        position_size_method=PositionSizeMethod.FIXED_QUANTITY,
        position_size_value=7.0,
    )

    result = make_engine(make_ohlcv_df([0.0, 100.0]), BuyFirstBarStrategy(), config).run()

    assert result.trades == []
