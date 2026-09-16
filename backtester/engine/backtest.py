"""Core event-driven backtest loop."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import cast

import pandas as pd

from backtester.data.loader import DataLoader
from backtester.engine.config import BacktestConfig, ExecutionPolicy
from backtester.engine.risk import risk_exit_reason
from backtester.engine.sizing import calculate_buy_quantity
from backtester.portfolio import Decision, Fill, Order, OrderEvent, OrderStatus, Portfolio, Side, Trade
from backtester.strategy import Signal, Strategy


@dataclass
class BacktestResult:
    """Output of a completed backtest run."""

    config: BacktestConfig
    strategy_name: str
    equity_curve: pd.Series
    trades: list[Trade]
    final_value: float
    initial_value: float
    decisions: list[Decision] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    order_events: list[OrderEvent] = field(default_factory=list)


class BacktestEngine:
    """Compose data, strategy, and portfolio components into a backtest."""

    def __init__(
        self,
        loader: DataLoader,
        strategy: Strategy,
        config: BacktestConfig,
    ) -> None:
        self._loader = loader
        self._strategy = strategy
        self._config = config

    def run(self) -> BacktestResult:
        data = self._loader.fetch(
            self._config.ticker,
            self._config.start_date,
            self._config.end_date,
        )
        portfolio = Portfolio(
            initial_cash=self._config.initial_cash,
            commission_rate=self._config.commission_rate,
        )
        close_array = data["close"].to_numpy(dtype=float)
        open_array = data["open"].to_numpy(dtype=float)
        timestamps = pd.to_datetime(data.index).to_pydatetime()
        first_bar = 0
        if self._config.evaluation_start is not None:
            first_bar = int(data.index.searchsorted(pd.Timestamp(self._config.evaluation_start)))
            if first_bar >= len(data):
                msg = "No bars on or after evaluation_start."
                raise ValueError(msg)
        decisions: list[Decision] = []
        orders: list[Order] = []
        fills: list[Fill] = []
        order_events: list[OrderEvent] = []
        pending_order: Order | None = None
        peak_close = 0.0

        for i in range(first_bar, len(data)):
            timestamp = cast(datetime, timestamps[i])
            current_price = float(close_array[i])

            if pending_order is not None:
                self._execute_and_record(
                    pending_order,
                    float(open_array[i]),
                    timestamp,
                    portfolio,
                    fills,
                    order_events,
                )
                pending_order = None

            # The strategy receives a bounded snapshot, so future rows are not
            # reachable from the decision method. Built-in causal features are
            # recomputed against this snapshot until a bounded feature API is
            # introduced.
            history = data.iloc[: i + 1].copy()
            self._strategy.precompute(history)
            signal = self._strategy.generate_signal(history, current_index=i)
            reason = ""
            position = portfolio.get_position(self._config.ticker)
            if position is None:
                peak_close = 0.0
            else:
                peak_close = max(peak_close, position.avg_entry_price, current_price)
                exit_reason = risk_exit_reason(
                    self._config,
                    entry_price=position.avg_entry_price,
                    peak_close=peak_close,
                    close=current_price,
                )
                if exit_reason is not None and signal is not Signal.SELL:
                    signal, reason = Signal.SELL, exit_reason
            decision = Decision(
                decision_id=f"D{i:08d}",
                ticker=self._config.ticker,
                signal=signal.name,
                decision_time=timestamp,
                information_cutoff=timestamp,
                reason=reason,
            )
            decisions.append(decision)
            order = self._signal_to_order(
                signal,
                self._config.ticker,
                timestamp,
                current_price,
                portfolio,
                history,
                i,
                decision.decision_id,
                len(orders),
            )
            if order is not None:
                orders.append(order)
                order_events.append(OrderEvent(order.order_id, OrderStatus.SUBMITTED, timestamp))
                if self._config.execution_policy is ExecutionPolicy.SAME_CLOSE:
                    self._execute_and_record(
                        order,
                        current_price,
                        timestamp,
                        portfolio,
                        fills,
                        order_events,
                    )
                else:
                    pending_order = order

            portfolio.record_equity(timestamp, {self._config.ticker: current_price})

        if pending_order is not None:
            order_events.append(
                OrderEvent(
                    pending_order.order_id,
                    OrderStatus.EXPIRED,
                    cast(datetime, timestamps[-1]),
                    "No later bar was available for execution.",
                )
            )

        final_close = float(close_array[-1])
        return BacktestResult(
            config=self._config,
            strategy_name=self._strategy.name,
            equity_curve=portfolio.get_equity_curve(),
            trades=portfolio.trade_history,
            final_value=portfolio.total_value({self._config.ticker: final_close}),
            initial_value=self._config.initial_cash,
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
        # Buys are sized at the decision close but fill at a later price. When a
        # gap makes the order unaffordable, fill what cash covers instead of
        # silently dropping the position.
        reason = ""
        if order.side is Side.BUY:
            affordable = portfolio.affordable_quantity(reference_price, self._config.slippage_bps)
            if 0 < affordable < order.quantity:
                reason = f"Quantity reduced from {order.quantity} to {affordable} to fit available cash."
                order = replace(order, quantity=affordable)
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
        order_events.append(OrderEvent(order.order_id, OrderStatus.FILLED, timestamp, reason))

    def _signal_to_order(
        self,
        signal: Signal,
        ticker: str,
        timestamp: datetime,
        current_price: float,
        portfolio: Portfolio,
        data: pd.DataFrame,
        current_index: int,
        decision_id: str,
        order_index: int,
    ) -> Order | None:
        if signal is Signal.HOLD:
            return None

        if signal is Signal.BUY:
            portfolio_value = portfolio.total_value({ticker: current_price})
            quantity = calculate_buy_quantity(
                config=self._config,
                price=current_price,
                available_cash=portfolio.cash,
                portfolio_value=portfolio_value,
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
