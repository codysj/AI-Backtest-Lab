"""Multi-asset event-driven backtest engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import cast

import pandas as pd

from backtester.data.loader import DataLoader
from backtester.engine.config import ExecutionPolicy, MultiAssetBacktestConfig
from backtester.engine.risk import risk_exit_reason
from backtester.engine.sizing import calculate_buy_quantity
from backtester.portfolio import Decision, Fill, Order, OrderEvent, OrderStatus, Portfolio, Side, Trade
from backtester.strategy import MultiAssetStrategy, Signal


@dataclass
class MultiAssetBacktestResult:
    """Output of a completed multi-asset backtest."""

    config: MultiAssetBacktestConfig
    strategy_name: str
    equity_curve: pd.Series
    trades: list[Trade]
    final_value: float
    initial_value: float
    price_data: dict[str, pd.DataFrame]
    benchmark_equity: pd.Series | None = None
    decisions: list[Decision] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    order_events: list[OrderEvent] = field(default_factory=list)


class MultiAssetBacktestEngine:
    """Compose loader, multi-asset strategy, and portfolio over many tickers.

    DataFrames are aligned on the intersection of all trading dates. Signals are
    processed in config ticker order, so competing BUY orders may consume cash
    before later tickers are reached. In multi-asset mode, ALL_IN uses all
    currently available cash for each BUY as it is processed.
    """

    def __init__(
        self,
        loader: DataLoader,
        strategy: MultiAssetStrategy,
        config: MultiAssetBacktestConfig,
    ) -> None:
        self._loader = loader
        self._strategy = strategy
        self._config = config

    def run(self) -> MultiAssetBacktestResult:
        aligned_data = self._load_and_align_data()
        portfolio = Portfolio(
            initial_cash=self._config.initial_cash,
            commission_rate=self._config.commission_rate,
        )
        close_arrays = {
            ticker: frame["close"].to_numpy(dtype=float)
            for ticker, frame in aligned_data.items()
        }
        open_arrays = {
            ticker: frame["open"].to_numpy(dtype=float)
            for ticker, frame in aligned_data.items()
        }
        shared_index = next(iter(aligned_data.values())).index
        timestamps = pd.to_datetime(shared_index).to_pydatetime()
        decisions: list[Decision] = []
        orders: list[Order] = []
        fills: list[Fill] = []
        order_events: list[OrderEvent] = []
        pending_orders: list[Order] = []
        peak_closes: dict[str, float] = {}

        for current_index in range(len(shared_index)):
            timestamp = cast(datetime, timestamps[current_index])
            current_prices = {
                ticker: float(close_arrays[ticker][current_index])
                for ticker in self._config.tickers
            }
            for pending_order in pending_orders:
                self._execute_and_record(
                    pending_order,
                    float(open_arrays[pending_order.ticker][current_index]),
                    timestamp,
                    portfolio,
                    fills,
                    order_events,
                )
            pending_orders = []

            history = {
                ticker: frame.iloc[: current_index + 1].copy()
                for ticker, frame in aligned_data.items()
            }
            self._strategy.precompute(history)
            signals = self._strategy.generate_signals(history, current_index)

            for ticker in self._config.tickers:
                signal = signals.get(ticker, Signal.HOLD)
                reason = ""
                position = portfolio.get_position(ticker)
                if position is None:
                    peak_closes.pop(ticker, None)
                else:
                    close = current_prices[ticker]
                    peak = max(peak_closes.get(ticker, 0.0), position.avg_entry_price, close)
                    peak_closes[ticker] = peak
                    exit_reason = risk_exit_reason(
                        self._config,
                        entry_price=position.avg_entry_price,
                        peak_close=peak,
                        close=close,
                    )
                    if exit_reason is not None and signal is not Signal.SELL:
                        signal, reason = Signal.SELL, exit_reason
                decision = Decision(
                    decision_id=f"D{current_index:08d}-{ticker}",
                    ticker=ticker,
                    signal=signal.name,
                    decision_time=timestamp,
                    information_cutoff=timestamp,
                    reason=reason,
                )
                decisions.append(decision)
                order = self._signal_to_order(
                    signal=signal,
                    ticker=ticker,
                    timestamp=timestamp,
                    current_price=current_prices[ticker],
                    current_prices=current_prices,
                    portfolio=portfolio,
                    data=history[ticker],
                    current_index=current_index,
                    decision_id=decision.decision_id,
                    order_index=len(orders),
                )
                if order is not None:
                    orders.append(order)
                    order_events.append(OrderEvent(order.order_id, OrderStatus.SUBMITTED, timestamp))
                    if self._config.execution_policy is ExecutionPolicy.SAME_CLOSE:
                        self._execute_and_record(
                            order,
                            current_prices[ticker],
                            timestamp,
                            portfolio,
                            fills,
                            order_events,
                        )
                    else:
                        pending_orders.append(order)

            portfolio.record_equity(timestamp, current_prices)

        for pending_order in pending_orders:
            order_events.append(
                OrderEvent(
                    pending_order.order_id,
                    OrderStatus.EXPIRED,
                    cast(datetime, timestamps[-1]),
                    "No later bar was available for execution.",
                )
            )

        final_prices = {
            ticker: float(close_arrays[ticker][-1])
            for ticker in self._config.tickers
        }
        return MultiAssetBacktestResult(
            config=self._config,
            strategy_name=self._strategy.name,
            equity_curve=portfolio.get_equity_curve(),
            trades=portfolio.trade_history,
            final_value=portfolio.total_value(final_prices),
            initial_value=self._config.initial_cash,
            price_data={ticker: frame.copy() for ticker, frame in aligned_data.items()},
            decisions=decisions,
            orders=orders,
            fills=fills,
            order_events=order_events,
        )

    def _execute_and_record(
        self,
        order: Order,
        reference_price: float,
        timestamp: datetime,
        portfolio: Portfolio,
        fills: list[Fill],
        order_events: list[OrderEvent],
    ) -> None:
        trade = portfolio.execute_order(
            order,
            reference_price,
            slippage_bps=self._config.slippage_bps,
            fill_timestamp=timestamp,
        )
        if trade is None:
            order_events.append(
                OrderEvent(order.order_id, OrderStatus.REJECTED, timestamp, "Portfolio constraints rejected the order.")
            )
            return
        fills.append(
            Fill(
                order_id=order.order_id,
                ticker=trade.ticker,
                side=trade.side,
                quantity=trade.quantity,
                reference_price=reference_price,
                price=trade.price,
                commission=trade.commission,
                filled_at=trade.timestamp,
            )
        )
        order_events.append(OrderEvent(order.order_id, OrderStatus.FILLED, timestamp))

    def _load_and_align_data(self) -> dict[str, pd.DataFrame]:
        raw_data = {
            ticker: self._loader.fetch(ticker, self._config.start_date, self._config.end_date)
            for ticker in self._config.tickers
        }
        common_index: pd.Index | None = None
        for frame in raw_data.values():
            common_index = frame.index if common_index is None else common_index.intersection(frame.index)
        if common_index is None or len(common_index) == 0:
            msg = "No common dates found across requested tickers."
            raise ValueError(msg)

        common_index = common_index.sort_values()
        return {
            ticker: frame.loc[common_index].sort_index().copy()
            for ticker, frame in raw_data.items()
        }

    def _signal_to_order(
        self,
        *,
        signal: Signal,
        ticker: str,
        timestamp: datetime,
        current_price: float,
        current_prices: dict[str, float],
        portfolio: Portfolio,
        data: pd.DataFrame,
        current_index: int,
        decision_id: str,
        order_index: int,
    ) -> Order | None:
        if signal is Signal.HOLD:
            return None
        if signal is Signal.BUY:
            quantity = calculate_buy_quantity(
                config=self._config,
                price=current_price,
                available_cash=portfolio.cash,
                portfolio_value=portfolio.total_value(current_prices),
                data=data,
                current_index=current_index,
            )
            if quantity <= 0:
                return None
            return Order(
                ticker=ticker,
                side=Side.BUY,
                quantity=quantity,
                timestamp=timestamp,
                order_id=f"O{order_index:08d}",
                decision_id=decision_id,
            )

        position = portfolio.get_position(ticker)
        if position is None:
            return None
        return Order(
            ticker=ticker,
            side=Side.SELL,
            quantity=position.quantity,
            timestamp=timestamp,
            order_id=f"O{order_index:08d}",
            decision_id=decision_id,
        )
