"""Registry, new strategies, indicators, protective exits, and DSL additions."""

from __future__ import annotations

from typing import get_args

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from backtester.ai.compiler import compile_strategy_draft
from backtester.ai.providers import FakeStrategyDraftProvider
from backtester.ai.schemas import StrategyDraftRequest, StrategyDraftStatus
from backtester.api.schemas import BacktestRequest, ResearchStrategyId, StrategyId
from backtester.engine import BacktestConfig, BacktestEngine
from backtester.strategy import STRATEGIES, IndicatorSpec, RuleBasedStrategy, RuleBasedStrategySpec, Signal, Strategy
from backtester.strategy import indicators
from backtester.strategy.oscillators import DonchianBreakoutStrategy, MacdCrossoverStrategy, RsiReversionStrategy
from tests.test_engine import FakeLoader, make_ohlcv_df


def random_walk(length: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.015, length)))
    frame = make_ohlcv_df(close.tolist())
    frame["high"] = frame["close"] * 1.01
    frame["low"] = frame["close"] * 0.99
    return frame


def test_api_literals_match_registry() -> None:
    assert set(get_args(ResearchStrategyId)) == set(STRATEGIES)
    assert set(get_args(StrategyId)) == set(STRATEGIES) | {"rule_based"}


@pytest.mark.parametrize("strategy_id", sorted(STRATEGIES))
def test_registry_strategies_are_causal(strategy_id: str) -> None:
    """A decision at bar i must not change when later bars are appended."""
    data = random_walk()
    full: Strategy = STRATEGIES[strategy_id].build({})
    full.precompute(data)
    for i in range(0, len(data), 7):
        bounded = STRATEGIES[strategy_id].build({})
        history = data.iloc[: i + 1]
        bounded.precompute(history)
        assert bounded.generate_signal(history, i) == full.generate_signal(data, i), (strategy_id, i)


@pytest.mark.parametrize("strategy_id", sorted(STRATEGIES))
def test_registry_strategies_run_and_trade(strategy_id: str) -> None:
    config = BacktestConfig(ticker="TEST", start_date="2020-01-01", end_date="2021-12-31")
    result = BacktestEngine(FakeLoader(random_walk(400)), STRATEGIES[strategy_id].build({}), config).run()
    assert result.trades, strategy_id
    assert result.final_value > 0


def test_registry_build_rejects_unknown_and_fractional_parameters() -> None:
    with pytest.raises(ValueError, match="Unsupported parameter"):
        STRATEGIES["macd_crossover"].build({"window": 3})
    with pytest.raises(ValueError, match="integer"):
        STRATEGIES["donchian_breakout"].build({"entry_window": 20.5})
    with pytest.raises(ValueError, match="fast_span"):
        MacdCrossoverStrategy(fast_span=26, slow_span=12)
    with pytest.raises(ValueError, match="oversold"):
        RsiReversionStrategy(oversold=70, overbought=30)


def test_backtest_request_validates_through_registry() -> None:
    with pytest.raises(ValidationError, match="fast_span"):
        BacktestRequest(
            ticker="AAPL",
            start_date="2020-01-01",
            end_date="2021-01-01",
            strategy="macd_crossover",
            parameters={"fast_span": 30, "slow_span": 20},
        )


def test_rsi_extremes() -> None:
    rising = indicators.rsi(pd.Series(np.arange(1.0, 40.0)), 14)
    flat = indicators.rsi(pd.Series([5.0] * 40), 14)
    assert rising.iloc[-1] == 100.0
    assert flat.iloc[-1] == 50.0
    assert rising.iloc[:13].isna().all()


def test_donchian_buys_on_breakout_and_sells_on_breakdown() -> None:
    close = [10.0] * 5 + [12.0, 12.5, 9.0]
    data = make_ohlcv_df(close)
    strategy = DonchianBreakoutStrategy(entry_window=3, exit_window=2)
    strategy.precompute(data)
    signals = [strategy.generate_signal(data, i) for i in range(len(data))]
    assert signals[5] is Signal.BUY
    assert signals[6] is Signal.HOLD  # continuation is not a second entry
    assert signals[7] is Signal.SELL


class BuyOnceStrategy(Strategy):
    @property
    def name(self) -> str:
        return "BuyOnce"

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> Signal:
        return Signal.BUY if current_index == 0 else Signal.HOLD


def run_with_exits(close: list[float], **exits: float) -> tuple[list[str], list[str]]:
    config = BacktestConfig(ticker="TEST", start_date="2020-01-01", end_date="2020-12-31", commission_rate=0, slippage_bps=0, **exits)
    result = BacktestEngine(FakeLoader(make_ohlcv_df(close)), BuyOnceStrategy(), config).run()
    return [trade.side.value for trade in result.trades], [d.reason for d in result.decisions if d.reason]


def test_stop_loss_exits_at_next_open_with_reason() -> None:
    sides, reasons = run_with_exits([100, 100, 94, 90, 80], stop_loss_pct=0.05)
    assert sides == ["BUY", "SELL"]
    assert reasons == ["STOP_LOSS"]


def test_take_profit_and_trailing_stop() -> None:
    assert run_with_exits([100, 100, 111, 115], take_profit_pct=0.1)[1] == ["TAKE_PROFIT"]
    sides, reasons = run_with_exits([100, 100, 130, 120, 115, 110], trailing_stop_pct=0.1)
    assert sides == ["BUY", "SELL"]
    assert reasons == ["TRAILING_STOP"]


def test_no_exit_without_configuration() -> None:
    assert run_with_exits([100, 100, 50, 40]) == (["BUY"], [])


def test_risk_exit_bounds_are_validated() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        BacktestConfig(ticker="T", start_date="2020-01-01", end_date="2020-02-01", stop_loss_pct=1.5)


def test_rule_dsl_supports_rsi_and_constant_values() -> None:
    spec = RuleBasedStrategySpec.model_validate(
        {
            "rules": {
                "entry": [{"left": {"name": "rsi", "window": 5}, "operator": "<", "right": {"name": "value", "value": 30}}],
                "exit": [{"left": {"name": "close"}, "operator": ">", "right": {"name": "ema", "window": 5}}],
            }
        }
    )
    data = make_ohlcv_df([10, 9, 8, 7, 6, 5, 4, 5, 6, 7, 8])
    strategy = RuleBasedStrategy(spec)
    strategy.precompute(data)
    assert strategy.generate_signal(data, 6) is Signal.BUY
    assert strategy.generate_signal(data, 10) is Signal.SELL
    with pytest.raises(ValidationError, match="value requires value"):
        IndicatorSpec.model_validate({"name": "value"})
    with pytest.raises(ValidationError, match="does not accept value"):
        IndicatorSpec.model_validate({"name": "sma", "window": 5, "value": 3})


def test_fake_provider_drafts_and_compiles_new_strategy_kinds() -> None:
    draft = FakeStrategyDraftProvider().draft_strategy(
        StrategyDraftRequest(prompt="Grid search an RSI strategy on MSFT from 2019 to 2023")
    )
    assert draft.strategy_kind.value == "rsi_reversion"
    assert draft.ticker == "MSFT"
    compiled = compile_strategy_draft(draft)
    assert compiled.status == StrategyDraftStatus.READY
    assert compiled.payload is not None
    assert compiled.payload["strategy"] == "rsi_reversion"
    assert set(compiled.payload["parameter_grid"]) == {"window", "oversold", "overbought"}


def test_evaluation_start_warms_indicators_without_trading_or_scoring() -> None:
    data = random_walk(160, seed=2)  # crossovers at bars 109-146, inside the evaluation window
    start = str(data.index[100].date())
    strategy_factory = lambda: STRATEGIES["momentum"].build({"fast_window": 5, "slow_window": 50})  # noqa: E731
    cold_config = BacktestConfig(ticker="T", start_date=start, end_date="2030-01-01")
    warm_config = BacktestConfig(ticker="T", start_date="2020-01-01", end_date="2030-01-01", evaluation_start=start)

    cold = BacktestEngine(FakeLoader(data.loc[start:]), strategy_factory(), cold_config).run()
    warm = BacktestEngine(FakeLoader(data), strategy_factory(), warm_config).run()

    assert warm.equity_curve.index[0] == data.index[100]
    assert len(warm.equity_curve) == len(cold.equity_curve) == 60
    assert all(fill.filled_at >= data.index[100] for fill in warm.fills)
    # Warm-up signals match an uninterrupted run over the same bars; a cold start does not.
    full = BacktestEngine(FakeLoader(data), strategy_factory(), BacktestConfig(ticker="T", start_date="2020-01-01", end_date="2030-01-01")).run()
    full_signals = [d.signal for d in full.decisions[100:]]
    assert [d.signal for d in warm.decisions] == full_signals
    assert [d.signal for d in cold.decisions] != full_signals
    with pytest.raises(ValueError, match="evaluation_start"):
        BacktestConfig(ticker="T", start_date="2020-01-01", end_date="2020-06-01", evaluation_start="2021-01-01")


def test_gap_up_fill_is_clipped_to_available_cash() -> None:
    data = make_ohlcv_df([100.0, 120.0, 120.0], open_prices=[100.0, 120.0, 120.0])
    config = BacktestConfig(ticker="T", start_date="2020-01-01", end_date="2020-12-31", slippage_bps=5)
    result = BacktestEngine(FakeLoader(data), BuyOnceStrategy(), config).run()

    assert result.orders[0].quantity == 950  # sized at the 100 close
    assert len(result.fills) == 1
    filled = result.fills[0]
    assert filled.quantity < 950
    assert filled.quantity * filled.price + filled.commission <= config.initial_cash
    assert "reduced" in result.order_events[-1].reason
