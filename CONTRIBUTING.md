# Contributing

Thanks for your interest in tradepilot. This doc covers how to get a
development environment working, the coding conventions used across the
codebase, and what we look for in a pull request.

## Local setup

```bash
git clone https://github.com/anthropics/tradepilot.git
cd tradepilot
uv sync --extra dev
uv run pytest
uv run ruff check
```

`uv` manages the venv and lock file. `ruff` formats and lints.

## Running the stack

For development you usually want the minimal compose file and the chat UI:

```bash
docker compose -f docker-compose.minimal.yml up --build
uv run streamlit run tools/chat_ui.py
```

## Coding conventions

- **TDD.** Start from a failing test, write minimal impl, get green. Every
  `feat:` commit should land with matching tests.
- **One commit per task.** Commit messages follow
  `<type>: <short description>` with types `feat`, `fix`, `chore`, `docs`,
  `test`, `refactor`. No co-author trailers unless requested.
- **`ruff check` + `ruff format` clean** before every commit.
- **Async first.** All I/O is async. Wrap synchronous SDKs with
  `asyncio.to_thread`.
- **Explicit over implicit.** Pydantic for every data contract. No dicts
  crossing module boundaries when a model would do.
- **US markets, English.** v0.1 is deliberately scoped.

## Safety-critical paths

Changes that touch:

- `gateway/services/paper_trading_alpaca.py`
- `src/models/order.py` (HMAC signing)
- `src/agent/nodes/{confirmation_classifier,confirmation,execute_trade}.py`
- Validator paper-mode rules in `src/agent/nodes/validator.py`

must:

1. Keep the `_assert_paper()` invariant (runs before every I/O).
2. Preserve the 60-second TTL + HMAC semantics of the confirmation token.
3. Land with tests that cover the adversarial path (tampered draft, expired
   draft, non-paper base URL).

Reviewers will look for these explicitly. If your PR loosens any of them,
please flag it in the description.

## Filing a PR

- Keep PRs focused. One topic per PR.
- Include test output (`uv run pytest -q` summary) in the description if
  the change is non-trivial.
- Link the issue you're resolving.
- Describe any new config vars in `.env.example` and in
  `docs/reference/configuration.md`.

## License

By contributing you agree your work is licensed under Apache 2.0.
