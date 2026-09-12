"""Portfolio cash, position, trade, and equity-curve management."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from backtester.portfolio.order import Order, Side, Trade
from backtester.portfolio.position import Position


class Portfolio:
    """Mutable portfolio state for simulated order execution."""

    def __init__(self, initial_cash: float, commission_rate: float = 0.001) -> None:
        if initial_cash <= 0:
            msg = "initial_cash must be positive."
            raise ValueError(msg)
        if commission_rate < 0:
            msg = "commission_rate must be non-negative."
            raise ValueError(msg)

        self._cash = initial_cash
        # Commission is modeled as a simple per-share charge.
        self._commission_rate = commission_rate
        self._positions: dict[str, Position] = {}
        self._trade_history: list[Trade] = []
        self._equity_curve: list[tuple[datetime, float]] = []

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def trade_history(self) -> list[Trade]:
        return list(self._trade_history)

    def get_position(self, ticker: str) -> Position | None:
        return self._positions.get(ticker)

    def execute_order(
        self,
        order: Order,
        fill_price: float,
        slippage_bps: float = 5.0,
        fill_timestamp: datetime | None = None,
    ) -> Trade | None:
        """Execute an order or return None when it is normally rejected.

        Slippage is simplified basis-point slippage: buys fill higher and sells
        fill lower. Order rejection returns None because rejected orders are
        ordinary simulation behavior, not bugs.
        """
        if order.quantity <= 0:
            return None
        if fill_price <= 0:
            msg = "fill_price must be positive."
            raise ValueError(msg)
        if slippage_bps < 0:
            msg = "slippage_bps must be non-negative."
            raise ValueError(msg)

        actual_price = self._apply_slippage(fill_price, order.side, slippage_bps)
        commission = self._commission_rate * order.quantity
        trade = Trade(
            ticker=order.ticker,
            side=order.side,
            quantity=order.quantity,
            price=actual_price,
            commission=commission,
            timestamp=fill_timestamp if fill_timestamp is not None else order.timestamp,
        )

        if order.side is Side.BUY:
            return self._execute_buy(trade)
        return self._execute_sell(trade)

    def total_value(self, current_prices: dict[str, float]) -> float:
        total = self._cash
        for ticker, position in self._positions.items():
            if ticker not in current_prices:
                msg = f"Missing current price for held ticker: {ticker}"
                raise KeyError(msg)
            total += position.quantity * current_prices[ticker]
        return total

    def record_equity(self, timestamp: datetime, current_prices: dict[str, float]) -> None:
        self._equity_curve.append((timestamp, self.total_value(current_prices)))

    def get_equity_curve(self) -> pd.Series:
        if not self._equity_curve:
            return pd.Series(
                index=pd.DatetimeIndex([], name="date"),
                dtype="float64",
                name="equity",
            )

        timestamps = [item[0] for item in self._equity_curve]
        values = [item[1] for item in self._equity_curve]
        return pd.Series(
            values,
            index=pd.DatetimeIndex(timestamps, name="date"),
            dtype="float64",
            name="equity",
        )

    def _execute_buy(self, trade: Trade) -> Trade | None:
        if trade.cost > self._cash:
            return None

        # Cash is rounded to cents after each mutation; production systems
        # would typically use Decimal for money.
        self._cash = round(self._cash - trade.cost, 2)
        position = self._positions.get(trade.ticker)
        if position is None:
            self._positions[trade.ticker] = Position(
                ticker=trade.ticker,
                quantity=trade.quantity,
                avg_entry_price=trade.price,
            )
        else:
            position.update_on_buy(trade.quantity, trade.price)

        self._trade_history.append(trade)
        return trade

    def _execute_sell(self, trade: Trade) -> Trade | None:
        position = self._positions.get(trade.ticker)
        if position is None or trade.quantity > position.quantity:
            return None

        self._cash = round(self._cash - trade.cost, 2)
        position.update_on_sell(trade.quantity)
        if position.quantity == 0:
            # Quantity-zero positions are removed so open positions stay clean.
            del self._positions[trade.ticker]

        self._trade_history.append(trade)
        return trade

    def _apply_slippage(self, fill_price: float, side: Side, slippage_bps: float) -> float:
        slippage_multiplier = slippage_bps / 10_000
        if side is Side.BUY:
            return fill_price * (1 + slippage_multiplier)
        return fill_price * (1 - slippage_multiplier)
