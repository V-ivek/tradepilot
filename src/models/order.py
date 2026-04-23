"""OrderDraft + HMAC-signed confirmation token.

The token is signed at ``prepare_order`` time over *all* order fields plus a
nonce and a creation timestamp. Any mutation invalidates it; any draft older
than ``TOKEN_TTL_SECONDS`` is rejected. ``hmac.compare_digest`` is used for
constant-time comparison to avoid a timing side-channel.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

TOKEN_TTL_SECONDS = 60


class OrderDraft(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    qty: Decimal = Field(gt=0)
    type: Literal["market", "limit", "stop", "stop_limit"]
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"
    estimated_cost: Decimal
    confirmation_token: str
    nonce: str
    created_at: datetime
    mode: Literal["paper"] = "paper"

    @model_validator(mode="after")
    def _price_required_for_type(self) -> "OrderDraft":
        if self.type in ("limit", "stop_limit") and self.limit_price is None:
            raise ValueError(f"limit_price required for order type {self.type}")
        if self.type in ("stop", "stop_limit") and self.stop_price is None:
            raise ValueError(f"stop_price required for order type {self.type}")
        return self


def _payload_for_signing(d: dict[str, Any]) -> bytes:
    created_at = d["created_at"]
    if isinstance(created_at, datetime):
        created_at_str = created_at.isoformat()
    else:
        created_at_str = str(created_at)
    parts = [
        str(d["symbol"]),
        str(d["side"]),
        str(d["qty"]),
        str(d["type"]),
        "" if d.get("limit_price") is None else str(d["limit_price"]),
        "" if d.get("stop_price") is None else str(d["stop_price"]),
        str(d["time_in_force"]),
        str(d["nonce"]),
        created_at_str,
    ]
    return "|".join(parts).encode("utf-8")


def sign_order(d: dict[str, Any], secret: str) -> str:
    return hmac.new(secret.encode(), _payload_for_signing(d), hashlib.sha256).hexdigest()


def verify_order_token(draft: OrderDraft, secret: str) -> bool:
    expected = sign_order(draft.model_dump(), secret)
    if not hmac.compare_digest(draft.confirmation_token, expected):
        return False
    created = draft.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - created).total_seconds()
    return 0 <= age <= TOKEN_TTL_SECONDS


def new_nonce() -> str:
    return secrets.token_hex(16)
