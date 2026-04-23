# Confirmation gate

The confirmation gate is the load-bearing safety component. Its job is to
make placing a paper order a **two-turn** operation — the LLM never has the
authority to submit an order single-turn.

## Two-turn flow

```mermaid
sequenceDiagram
    participant U as User
    participant G as guard
    participant T as trade_agent
    participant CG as confirmation_gate
    participant C as confirmation_classifier
    participant E as execute_trade

    U->>G: "buy 10 TSLA"
    G->>T: category=trade
    T->>T: prepare_order → signed OrderDraft
    T->>CG: state.awaiting_confirmation=True
    CG-->>U: trade_intent block (PAPER)
    Note over CG: turn ends; graph state checkpointed

    U->>G: "confirm"
    Note over G: awaiting_confirmation=True → classifier
    G->>C: classify
    C->>E: AFFIRM
    E->>E: verify_order_token; TTL check; place_order
    E-->>U: order_result block
```

## The HMAC token

`prepare_order` builds an `OrderDraft` with an HMAC-SHA256 signature over all
order fields + a nonce + `created_at`. The token has a **60-second TTL**.

- Any mutation of order fields invalidates the token (signature mismatch).
- Elapsed time beyond 60 s rejects the draft regardless of signature.
- The secret is `JWT_SECRET`. Rotating it invalidates all pending drafts.

## Why two turns

A human-in-the-loop confirmation is the entire point. Letting the LLM
tool-call-and-execute in one turn gives the model authority to place orders
— the design prevents that.

LangGraph's interrupt primitive is purpose-built for this: pause, persist,
resume. The safety property is testable: *"graph halts at
confirmation_gate with pending_trade set after any trade request."*
