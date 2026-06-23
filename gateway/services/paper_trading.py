"""Paper trading port (Protocol) and request/response DTOs.

Adapters implement this Protocol. Routes and tests depend on the Protocol,
never on a concrete adapter class.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop", "stop_limit"]
TimeInForce = Literal["day", "gtc", "ioc", "fok"]
OrderStatus = Literal[
    "new",
    "partially_filled",
    "filled",
    "canceled",
    "expired",
    "rejected",
    "failed",
]


class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    qty: Decimal
    type: OrderType
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce = "day"
    client_order_id: str | None = None


class OrderResult(BaseModel):
    order_id: str
    symbol: str
    side: OrderSide
    qty: Decimal
    type: OrderType
    status: OrderStatus
    filled_qty: Decimal
    filled_avg_price: Decimal | None
    submitted_at: datetime
    mode: Literal["paper"] = "paper"


class Position(BaseModel):
    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal
    unrealized_plpc: Decimal


class Account(BaseModel):
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    day_trade_count: int
    positions_count: int
    mode: Literal["paper"] = "paper"


class PortfolioHistory(BaseModel):
    timestamps: list[datetime]
    equity: list[Decimal]
    profit_loss: list[Decimal]
    base_value: Decimal


@runtime_checkable
class PaperTradingService(Protocol):
    async def get_account(self) -> Account: ...
    async def list_positions(self) -> list[Position]: ...
    async def list_orders(self, status: OrderStatus | None = None) -> list[OrderResult]: ...
    async def place_order(self, req: OrderRequest) -> OrderResult: ...
    async def cancel_order(self, order_id: str) -> None: ...
    async def get_portfolio_history(self, period: str = "1M") -> PortfolioHistory: ...
