"""In-memory ``PaperTradingService`` used by route + graph tests.

``place_order`` stores the order and immediately marks it ``filled`` at the
configured fill price (default $100). Enough to exercise order lifecycle
paths without hitting Alpaca.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from gateway.services.paper_trading import (
    Account,
    OrderRequest,
    OrderResult,
    OrderStatus,
    PortfolioHistory,
    Position,
)


class FakePaperTradingAdapter:
    def __init__(
        self,
        *,
        starting_cash: Decimal = Decimal("100000"),
        fill_price: Decimal = Decimal("100"),
    ):
        self._cash = starting_cash
        self._fill_price = fill_price
        self._orders: list[OrderResult] = []
        self._positions: dict[str, Position] = {}

    async def get_account(self) -> Account:
        equity = self._cash + sum((p.market_value for p in self._positions.values()), Decimal("0"))
        return Account(
            equity=equity,
            cash=self._cash,
            buying_power=self._cash,
            day_trade_count=0,
            positions_count=len(self._positions),
        )

    async def list_positions(self) -> list[Position]:
        return list(self._positions.values())

    async def list_orders(self, status: OrderStatus | None = None) -> list[OrderResult]:
        if status is None:
            return list(self._orders)
        return [o for o in self._orders if o.status == status]

    async def place_order(self, req: OrderRequest) -> OrderResult:
        fill_price = req.limit_price or self._fill_price
        result = OrderResult(
            order_id=str(uuid.uuid4()),
            symbol=req.symbol,
            side=req.side,
            qty=req.qty,
            type=req.type,
            status="filled",
            filled_qty=req.qty,
            filled_avg_price=fill_price,
            submitted_at=datetime.now(timezone.utc),
        )
        self._orders.append(result)

        notional = req.qty * fill_price
        if req.side == "buy":
            self._cash -= notional
            existing = self._positions.get(req.symbol)
            if existing:
                new_qty = existing.qty + req.qty
                new_cost = existing.avg_entry_price * existing.qty + notional
                self._positions[req.symbol] = Position(
                    symbol=req.symbol,
                    qty=new_qty,
                    avg_entry_price=new_cost / new_qty,
                    market_value=new_qty * fill_price,
                    unrealized_pl=Decimal("0"),
                    unrealized_plpc=Decimal("0"),
                )
            else:
                self._positions[req.symbol] = Position(
                    symbol=req.symbol,
                    qty=req.qty,
                    avg_entry_price=fill_price,
                    market_value=notional,
                    unrealized_pl=Decimal("0"),
                    unrealized_plpc=Decimal("0"),
                )
        else:  # sell
            self._cash += notional
            existing = self._positions.get(req.symbol)
            if existing:
                remaining = existing.qty - req.qty
                if remaining <= 0:
                    self._positions.pop(req.symbol, None)
                else:
                    self._positions[req.symbol] = existing.model_copy(
                        update={"qty": remaining, "market_value": remaining * fill_price}
                    )
        return result

    async def cancel_order(self, order_id: str) -> None:
        for i, o in enumerate(self._orders):
            if o.order_id == order_id:
                self._orders[i] = o.model_copy(update={"status": "canceled"})
                return

    async def get_portfolio_history(self, period: str = "1M") -> PortfolioHistory:
        now = datetime.now(timezone.utc)
        equity = self._cash + sum((p.market_value for p in self._positions.values()), Decimal("0"))
        return PortfolioHistory(
            timestamps=[now],
            equity=[equity],
            profit_loss=[equity - Decimal("100000")],
            base_value=Decimal("100000"),
        )
