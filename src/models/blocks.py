"""Response block types (SSE payloads).

Pydantic discriminated union keyed by the ``type`` field. Trading-related
blocks carry ``mode: Literal["paper"]`` non-optionally — the paper-trading
guarantee enforced at the schema level.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    content: str


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    columns: list[str]
    rows: list[list[str]]


class QuoteBlock(BaseModel):
    type: Literal["quote"] = "quote"
    symbol: str
    price: Decimal
    change: Decimal
    change_pct: Decimal


class ChartBlock(BaseModel):
    type: Literal["chart"] = "chart"
    symbol: str
    timeframe: str
    data: list[dict]


class NewsCardBlock(BaseModel):
    type: Literal["news_card"] = "news_card"
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    tickers: list[str] = []


class TradeIntentBlock(BaseModel):
    type: Literal["trade_intent"] = "trade_intent"
    symbol: str
    side: Literal["buy", "sell"]
    qty: Decimal
    order_type: Literal["market", "limit", "stop", "stop_limit"]
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"
    estimated_cost: Decimal
    confirmation_token: str
    mode: Literal["paper"]


class OrderResultBlock(BaseModel):
    type: Literal["order_result"] = "order_result"
    order_id: str
    status: str
    filled_qty: Decimal
    filled_avg_price: Decimal | None
    timestamp: datetime
    mode: Literal["paper"]


class AccountSummaryBlock(BaseModel):
    type: Literal["account_summary"] = "account_summary"
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    day_trade_count: int
    positions_count: int
    mode: Literal["paper"]


class PositionRow(BaseModel):
    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal
    unrealized_plpc: Decimal


class PositionsTableBlock(BaseModel):
    type: Literal["positions_table"] = "positions_table"
    rows: list[PositionRow]
    mode: Literal["paper"]


Block = Annotated[
    TextBlock
    | TableBlock
    | QuoteBlock
    | ChartBlock
    | NewsCardBlock
    | TradeIntentBlock
    | OrderResultBlock
    | AccountSummaryBlock
    | PositionsTableBlock,
    Field(discriminator="type"),
]
