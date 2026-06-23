# tradepilot

An open-source conversational AI trading assistant powered by Alpaca paper
trading. Ask questions in natural English about US stocks — news,
fundamentals, estimates, your portfolio — and place **paper** orders with
human-in-the-loop confirmation.

!!! warning "Paper only"
    tradepilot only connects to Alpaca's paper-trading endpoint. Live trading
    is **architecturally blocked**, not just disabled. See
    [Safety](overview/safety.md).

## Jump in

- [Quickstart](getting-started/quickstart.md) — clone, set keys, `docker compose up`.
- [System overview](architecture/system-overview.md) — how the pieces fit.
- [Confirmation gate](architecture/confirmation-gate.md) — the load-bearing safety component.

## License

Apache-2.0.
