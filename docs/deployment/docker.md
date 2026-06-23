# Docker

Two compose files. Pick one.

## Minimal (quickstart)

```bash
docker compose -f docker-compose.minimal.yml up --build
```

Three containers: `app`, `gateway`, `postgres`. No LiteLLM, no Langfuse, no
Redis. Uses `ANTHROPIC_API_KEY` directly, in-memory semantic cache, no
tracing. Fastest path to "clone and try it."

## Full stack

```bash
docker compose up --build
```

Seven containers: `app`, `gateway`, `litellm`, `langfuse`, `postgres`,
`redis`, `chat-ui`. Port map:

| Service | Host port |
|---|---|
| app | 4700 |
| litellm | 4701 |
| langfuse | 4702 |
| postgres | 4703 |
| redis | 4704 |
| chat-ui | 4705 |
| gateway | 4706 |

## Environment

Both stacks read `.env`. The gateway refuses to start unless its startup
paper-mode verification passes (see
[paper-trading safety](../architecture/paper-trading-safety.md)).
