# Adding a tool

Tools are thin wrappers over the gateway client. Each tool is its own file
so the LLM sees a focused docstring at binding time.

Template:

```python
# src/tools/stocks/my_tool.py
from langchain_core.tools import tool

from src.services.gateway import GatewayClient, get_gateway_client


async def _impl(gateway: GatewayClient, ticker: str) -> dict:
    data = await gateway.get_quote(ticker)
    return data.model_dump(mode="json") if data else {}


@tool
async def my_tool(ticker: str) -> dict:
    """One-line description the LLM reads when deciding to call this tool."""
    return await _impl(get_gateway_client(), ticker)
```

Tests: one case per branch of `_impl` using a fake gateway. See
`tests/unit/test_tools_non_trading.py` for the pattern.

Bind the tool into the agent by adding it to the agent's tools list (e.g.
`NEWS_TOOLS`, `STOCK_TOOLS`).
