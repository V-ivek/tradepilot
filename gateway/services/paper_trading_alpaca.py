"""Alpaca paper-trading adapter.

The entire point of this adapter is to make it architecturally impossible to
hit Alpaca's live endpoint:

1. Constructor forces ``paper=True``.
2. ``_assert_paper()`` runs before every public method's I/O and verifies the
   underlying client's base URL is the hardcoded paper URL.
3. The live URL is a hardcoded denylist constant; no config can override it.
4. Construction with the live URL raises — caught and re-raised as
   ``RuntimeError`` so uvicorn refuses to start.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaSide
from alpaca.trading.enums import OrderStatus as AlpacaOrderStatus
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.enums import TimeInForce as AlpacaTIF
from alpaca.trading.requests import (
    GetOrdersRequest,
    GetPortfolioHistoryRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLimitOrderRequest,
    StopOrderRequest,
)

from gateway.services.paper_trading import (
    Account,
    OrderRequest,
    OrderResult,
    OrderStatus,
    PortfolioHistory,
    Position,
)

logger = logging.getLogger(__name__)

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL_DENY = "https://api.alpaca.markets"

_SIDE_MAP: dict[str, AlpacaSide] = {"buy": AlpacaSide.BUY, "sell": AlpacaSide.SELL}
_TIF_MAP: dict[str, AlpacaTIF] = {
    "day": AlpacaTIF.DAY,
    "gtc": AlpacaTIF.GTC,
    "ioc": AlpacaTIF.IOC,
    "fok": AlpacaTIF.FOK,
}
_QUERY_STATUS_MAP: dict[str, QueryOrderStatus] = {
    "new": QueryOrderStatus.OPEN,
    "partially_filled": QueryOrderStatus.OPEN,
    "filled": QueryOrderStatus.CLOSED,
    "canceled": QueryOrderStatus.CLOSED,
    "expired": QueryOrderStatus.CLOSED,
    "rejected": QueryOrderStatus.CLOSED,
    "failed": QueryOrderStatus.CLOSED,
}
_STATUS_MAP: dict[AlpacaOrderStatus, OrderStatus] = {
    AlpacaOrderStatus.NEW: "new",
    AlpacaOrderStatus.PARTIALLY_FILLED: "partially_filled",
    AlpacaOrderStatus.FILLED: "filled",
    AlpacaOrderStatus.CANCELED: "canceled",
    AlpacaOrderStatus.EXPIRED: "expired",
    AlpacaOrderStatus.REJECTED: "rejected",
}


def _extract_base_url(client: TradingClient) -> str:
    raw = getattr(client, "_base_url", None)
    if raw is None:
        return ""
    return getattr(raw, "value", str(raw))


class AlpacaPaperTradingAdapter:
    def __init__(
        self,
        *,
        key_id: str,
        secret: str,
        client: TradingClient | None = None,
    ):
        self._client = client or TradingClient(api_key=key_id, secret_key=secret, paper=True)
        self._assert_paper()

    def _assert_paper(self) -> None:
        base = _extract_base_url(self._client)
        if base == LIVE_BASE_URL_DENY:
            raise RuntimeError("Refusing to run: Alpaca live endpoint is architecturally blocked.")
        if base != PAPER_BASE_URL:
            raise RuntimeError(
                f"Refusing to run: Alpaca adapter base_url={base!r} is not the paper endpoint."
            )

    async def _to_thread(self, fn, *args, **kwargs):
        self._assert_paper()
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def get_account(self) -> Account:
        raw = await self._to_thread(self._client.get_account)
        positions = await self._to_thread(self._client.get_all_positions)
        return Account(
            equity=Decimal(str(raw.equity)),
            cash=Decimal(str(raw.cash)),
            buying_power=Decimal(str(raw.buying_power)),
            day_trade_count=int(getattr(raw, "daytrade_count", 0) or 0),
            positions_count=len(positions or []),
        )

    async def list_positions(self) -> list[Position]:
        raw_positions = await self._to_thread(self._client.get_all_positions)
        out: list[Position] = []
        for p in raw_positions or []:
            try:
                out.append(
                    Position(
                        symbol=p.symbol,
                        qty=Decimal(str(p.qty)),
                        avg_entry_price=Decimal(str(p.avg_entry_price)),
                        market_value=Decimal(str(p.market_value)),
                        unrealized_pl=Decimal(str(p.unrealized_pl)),
                        unrealized_plpc=Decimal(str(p.unrealized_plpc)),
                    )
                )
            except Exception as e:
                logger.warning("skipping malformed position %r: %s", p, e)
        return out

    async def list_orders(self, status: OrderStatus | None = None) -> list[OrderResult]:
        query_status = _QUERY_STATUS_MAP.get(status) if status else None
        req = GetOrdersRequest(status=query_status) if query_status else GetOrdersRequest()
        raw_orders = await self._to_thread(self._client.get_orders, filter=req)
        return [self._map_order(o) for o in raw_orders or []]

    async def place_order(self, req: OrderRequest) -> OrderResult:
        alpaca_req = self._build_order_request(req)
        raw = await self._to_thread(self._client.submit_order, alpaca_req)
        return self._map_order(raw)

    async def cancel_order(self, order_id: str) -> None:
        await self._to_thread(self._client.cancel_order_by_id, order_id)

    async def get_portfolio_history(self, period: str = "1M") -> PortfolioHistory:
        req = GetPortfolioHistoryRequest(period=period)
        raw = await self._to_thread(self._client.get_portfolio_history, req)
        timestamps = [datetime.fromtimestamp(t, tz=timezone.utc) for t in (raw.timestamp or [])]
        equity = [Decimal(str(v)) for v in (raw.equity or [])]
        pl = [Decimal(str(v)) for v in (raw.profit_loss or [])]
        base_value = Decimal(str(getattr(raw, "base_value", 0) or 0))
        return PortfolioHistory(
            timestamps=timestamps, equity=equity, profit_loss=pl, base_value=base_value
        )

    def _build_order_request(self, req: OrderRequest):
        common: dict[str, Any] = {
            "symbol": req.symbol,
            "qty": float(req.qty),
            "side": _SIDE_MAP[req.side],
            "time_in_force": _TIF_MAP[req.time_in_force],
        }
        if req.client_order_id:
            common["client_order_id"] = req.client_order_id
        if req.type == "market":
            return MarketOrderRequest(**common)
        if req.type == "limit":
            if req.limit_price is None:
                raise ValueError("limit_price required for limit order")
            return LimitOrderRequest(**common, limit_price=float(req.limit_price))
        if req.type == "stop":
            if req.stop_price is None:
                raise ValueError("stop_price required for stop order")
            return StopOrderRequest(**common, stop_price=float(req.stop_price))
        if req.type == "stop_limit":
            if req.limit_price is None or req.stop_price is None:
                raise ValueError("stop_price and limit_price required for stop_limit order")
            return StopLimitOrderRequest(
                **common,
                stop_price=float(req.stop_price),
                limit_price=float(req.limit_price),
            )
        raise ValueError(f"Unknown order type: {req.type}")

    def _map_order(self, raw) -> OrderResult:
        alpaca_status = getattr(raw, "status", None)
        status: OrderStatus = _STATUS_MAP.get(alpaca_status, "new")
        side_raw = getattr(raw, "side", None)
        side: str = side_raw.value if hasattr(side_raw, "value") else str(side_raw or "buy")
        type_raw = getattr(raw, "type", None) or getattr(raw, "order_type", None)
        type_str = type_raw.value if hasattr(type_raw, "value") else str(type_raw or "market")
        if type_str not in ("market", "limit", "stop", "stop_limit"):
            type_str = "market"
        filled_avg = getattr(raw, "filled_avg_price", None)
        return OrderResult(
            order_id=str(raw.id),
            symbol=raw.symbol,
            side=side,  # type: ignore[arg-type]
            qty=Decimal(str(raw.qty)),
            type=type_str,  # type: ignore[arg-type]
            status=status,
            filled_qty=Decimal(str(getattr(raw, "filled_qty", 0) or 0)),
            filled_avg_price=Decimal(str(filled_avg)) if filled_avg is not None else None,
            submitted_at=getattr(raw, "submitted_at", None) or datetime.now(timezone.utc),
        )
