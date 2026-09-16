"""Order and trade primitives for portfolio simulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Side(Enum):
    """Order or trade direction."""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Lifecycle state recorded for a simulated order."""

    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class Decision:
    """Auditable strategy decision made with data through ``information_cutoff``."""

    decision_id: str
    ticker: str
    signal: str
    decision_time: datetime
    information_cutoff: datetime
    reason: str = ""


@dataclass(frozen=True)
class Order:
    """Intent to buy or sell a quantity of shares."""

    ticker: str
    side: Side
    quantity: int
    timestamp: datetime
    order_id: str = ""
    decision_id: str = ""


@dataclass(frozen=True)
class Fill:
    """Execution linked to the order that produced it."""

    order_id: str
    ticker: str
    side: Side
    quantity: int
    reference_price: float
    price: float
    commission: float
    filled_at: datetime


@dataclass(frozen=True)
class OrderEvent:
    """One immutable order lifecycle transition."""

    order_id: str
    status: OrderStatus
    timestamp: datetime
    reason: str = ""


@dataclass(frozen=True)
class Trade:
    """Executed order with fill price and commission."""

    ticker: str
    side: Side
    quantity: int
    price: float
    commission: float
    timestamp: datetime

    @property
    def cost(self) -> float:
        """Return cash impact where positive values are cash outflows."""
        gross_value = self.quantity * self.price
        if self.side is Side.BUY:
            return gross_value + self.commission
        return -(gross_value - self.commission)
