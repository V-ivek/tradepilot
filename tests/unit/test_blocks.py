from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from src.models.blocks import (
    AccountSummaryBlock,
    Block,
    ChartBlock,
    NewsCardBlock,
    OrderResultBlock,
    PositionRow,
    PositionsTableBlock,
    QuoteBlock,
    TableBlock,
    TextBlock,
    TradeIntentBlock,
)

BLOCK = TypeAdapter(Block)


def _roundtrip(model):
    return type(model).model_validate(model.model_dump(mode="json"))


def test_text_block_roundtrip():
    b = TextBlock(content="hi")
    assert _roundtrip(b) == b


def test_table_block_roundtrip():
    b = TableBlock(columns=["a", "b"], rows=[["1", "2"]])
    assert _roundtrip(b) == b


def test_quote_block_roundtrip():
    b = QuoteBlock(
        symbol="AAPL",
        price=Decimal("189.55"),
        change=Decimal("1.23"),
        change_pct=Decimal("0.65"),
    )
    assert _roundtrip(b) == b


def test_chart_block_roundtrip():
    b = ChartBlock(symbol="AAPL", timeframe="1M", data=[{"t": 1, "c": "1"}])
    assert _roundtrip(b) == b


def test_news_card_block_roundtrip():
    b = NewsCardBlock(
        title="t",
        summary="s",
        url="https://x",
        source="wire",
        published_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        tickers=["AAPL"],
    )
    assert _roundtrip(b) == b


def test_trade_intent_requires_mode_paper():
    with pytest.raises(ValidationError):
        TradeIntentBlock(
            symbol="AAPL",
            side="buy",
            qty=Decimal("1"),
            order_type="market",
            estimated_cost=Decimal("100"),
            confirmation_token="tok",
        )  # missing mode


def test_trade_intent_rejects_non_paper_mode():
    with pytest.raises(ValidationError):
        TradeIntentBlock(
            symbol="AAPL",
            side="buy",
            qty=Decimal("1"),
            order_type="market",
            estimated_cost=Decimal("100"),
            confirmation_token="tok",
            mode="live",
        )


def test_trade_intent_happy_path():
    b = TradeIntentBlock(
        symbol="AAPL",
        side="buy",
        qty=Decimal("1"),
        order_type="market",
        estimated_cost=Decimal("100"),
        confirmation_token="tok",
        mode="paper",
    )
    assert _roundtrip(b) == b


def test_order_result_requires_mode():
    with pytest.raises(ValidationError):
        OrderResultBlock(
            order_id="x",
            status="filled",
            filled_qty=Decimal("1"),
            filled_avg_price=Decimal("100"),
            timestamp=datetime.now(timezone.utc),
        )


def test_account_summary_roundtrip():
    b = AccountSummaryBlock(
        equity=Decimal("1"),
        cash=Decimal("1"),
        buying_power=Decimal("1"),
        day_trade_count=0,
        positions_count=0,
        mode="paper",
    )
    assert _roundtrip(b) == b


def test_positions_table_roundtrip():
    row = PositionRow(
        symbol="AAPL",
        qty=Decimal("1"),
        avg_entry_price=Decimal("100"),
        market_value=Decimal("110"),
        unrealized_pl=Decimal("10"),
        unrealized_plpc=Decimal("0.1"),
    )
    b = PositionsTableBlock(rows=[row], mode="paper")
    assert _roundtrip(b) == b


def test_discriminated_union_parses_each_type():
    for dumped in [
        {"type": "text", "content": "hi"},
        {
            "type": "trade_intent",
            "symbol": "AAPL",
            "side": "buy",
            "qty": "1",
            "order_type": "market",
            "estimated_cost": "100",
            "confirmation_token": "tok",
            "mode": "paper",
        },
    ]:
        parsed = BLOCK.validate_python(dumped)
        assert parsed.type == dumped["type"]
