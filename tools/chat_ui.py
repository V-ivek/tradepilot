"""Streamlit chat UI for tradepilot. Developer/demo use only.

Renders an amber PAPER banner at the top, streams SSE events from the app's
/chat endpoint, and renders each block type. Trade-intent blocks carry a
PAPER pill and a confirm/cancel row.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st
from jose import jwt

APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:4700")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGO = "HS256"


def _issue_token(user_id: str = "dev-user") -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        },
        JWT_SECRET,
        algorithm=JWT_ALGO,
    )


def _health() -> dict:
    try:
        r = requests.get(f"{APP_BASE_URL}/health", timeout=3)
        return r.json() if r.ok else {}
    except requests.RequestException:
        return {}


def _banner(health: dict) -> None:
    st.markdown(
        """
        <style>
        .paper-banner {
            background: #FFEDCC;
            color: #663300;
            padding: 10px 16px;
            border-radius: 6px;
            border: 1px solid #E6A23C;
            font-weight: 600;
            margin-bottom: 16px;
        }
        .paper-pill {
            background: #FFEDCC;
            color: #663300;
            padding: 2px 8px;
            border-radius: 10px;
            border: 1px solid #E6A23C;
            font-size: 0.75em;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    mode = health.get("trading_mode", "unknown").upper()
    st.markdown(
        f'<div class="paper-banner">⚠ {mode} TRADING MODE — no real money, no real orders</div>',
        unsafe_allow_html=True,
    )


def _render_block(block: dict) -> None:
    btype = block.get("type")
    if btype == "text":
        st.write(block.get("content", ""))
    elif btype == "quote":
        cols = st.columns(3)
        cols[0].metric(block["symbol"], f"${block['price']}")
        cols[1].metric("Change", f"${block.get('change', 0)}")
        cols[2].metric("Change %", f"{block.get('change_pct', 0)}%")
    elif btype == "chart":
        st.caption(f"{block['symbol']} — {block.get('timeframe', '')}")
        st.line_chart({"close": [float(row.get("close", 0)) for row in block.get("data", [])]})
    elif btype == "news_card":
        st.markdown(f"**[{block.get('title', '')}]({block.get('url', '#')})**")
        if block.get("summary"):
            st.caption(block["summary"])
    elif btype == "table":
        cols = block.get("columns", [])
        rows = block.get("rows", [])
        st.table({c: [r[i] for r in rows] for i, c in enumerate(cols)})
    elif btype == "account_summary":
        st.markdown('<span class="paper-pill">PAPER</span>', unsafe_allow_html=True)
        cols = st.columns(3)
        cols[0].metric("Equity", f"${block['equity']}")
        cols[1].metric("Cash", f"${block['cash']}")
        cols[2].metric("Buying power", f"${block['buying_power']}")
    elif btype == "positions_table":
        st.markdown('<span class="paper-pill">PAPER</span>', unsafe_allow_html=True)
        rows = block.get("rows", [])
        if rows:
            st.table(rows)
        else:
            st.caption("No open positions.")
    elif btype == "trade_intent":
        st.markdown('<span class="paper-pill">PAPER</span>', unsafe_allow_html=True)
        st.markdown(
            f"**{block['side'].upper()} {block['qty']} {block['symbol']}** — {block['order_type']}"
        )
        st.caption(f"Estimated cost: ${block['estimated_cost']}")
        cols = st.columns(2)
        if cols[0].button("Confirm (paper)", key=f"confirm-{block['confirmation_token']}"):
            st.session_state["send_confirm"] = True
        if cols[1].button("Cancel", key=f"cancel-{block['confirmation_token']}"):
            st.session_state["send_cancel"] = True
    elif btype == "order_result":
        st.markdown('<span class="paper-pill">PAPER</span>', unsafe_allow_html=True)
        st.success(
            f"Order {block['order_id']}: {block['status']} "
            f"({block.get('filled_qty', '')} @ {block.get('filled_avg_price', 'market')})"
        )
    else:
        st.json(block)


def _chat(user_input: str) -> list[dict]:
    token = _issue_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    body = {
        "user_input": user_input,
        "conversation_id": st.session_state.get("conversation_id"),
    }
    r = requests.post(f"{APP_BASE_URL}/chat", json=body, headers=headers, stream=True, timeout=60)
    blocks: list[dict] = []
    event = None
    for raw in r.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        if raw.startswith("event:"):
            event = raw[len("event:") :].strip()
        elif raw.startswith("data:"):
            payload = json.loads(raw[len("data:") :].strip())
            if event == "message_start":
                st.session_state["conversation_id"] = payload.get("conversation_id")
            elif event == "block":
                blocks.append(payload)
    return blocks


def main() -> None:
    st.set_page_config(page_title="tradepilot (paper)", page_icon="📈")
    health = _health()
    _banner(health)

    if "history" not in st.session_state:
        st.session_state["history"] = []

    for role, blocks in st.session_state["history"]:
        with st.chat_message(role):
            if role == "user":
                st.write(blocks)
            else:
                for b in blocks:
                    _render_block(b)

    user_input = st.chat_input("Ask about a stock, your paper account, or place a paper order…")

    # Handle button presses from a previously rendered trade_intent.
    if st.session_state.pop("send_confirm", False):
        user_input = "confirm"
    elif st.session_state.pop("send_cancel", False):
        user_input = "cancel"

    if user_input:
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state["history"].append(("user", user_input))

        with st.chat_message("assistant"):
            try:
                blocks = _chat(user_input)
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")
                blocks = []
            for b in blocks:
                _render_block(b)
        st.session_state["history"].append(("assistant", blocks))


if __name__ == "__main__":
    main()
