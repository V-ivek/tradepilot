from fastapi import APIRouter, Depends

from gateway.deps import get_paper_trading
from gateway.services.paper_trading import (
    Account,
    OrderRequest,
    OrderResult,
    OrderStatus,
    PaperTradingService,
    PortfolioHistory,
    Position,
)

router = APIRouter()


@router.get("/account", response_model=Account)
async def get_account(svc: PaperTradingService = Depends(get_paper_trading)) -> Account:
    return await svc.get_account()


@router.get("/positions", response_model=list[Position])
async def list_positions(
    svc: PaperTradingService = Depends(get_paper_trading),
) -> list[Position]:
    return await svc.list_positions()


@router.get("/orders", response_model=list[OrderResult])
async def list_orders(
    status: OrderStatus | None = None,
    svc: PaperTradingService = Depends(get_paper_trading),
) -> list[OrderResult]:
    return await svc.list_orders(status=status)


@router.post("/orders", response_model=OrderResult)
async def place_order(
    req: OrderRequest,
    svc: PaperTradingService = Depends(get_paper_trading),
) -> OrderResult:
    return await svc.place_order(req)


@router.delete("/orders/{order_id}", status_code=204)
async def cancel_order(
    order_id: str,
    svc: PaperTradingService = Depends(get_paper_trading),
) -> None:
    await svc.cancel_order(order_id)


@router.get("/portfolio/history", response_model=PortfolioHistory)
async def get_portfolio_history(
    period: str = "1M",
    svc: PaperTradingService = Depends(get_paper_trading),
) -> PortfolioHistory:
    return await svc.get_portfolio_history(period=period)
