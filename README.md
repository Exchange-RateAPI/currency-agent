# 💶💱 Exchange-RateAPI Currency Agent (A2A + ADK + MCP)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Powered by Exchange-RateAPI](https://img.shields.io/badge/Powered%20by-Exchange--RateAPI-blueviolet.svg)](https://exchange-rateapi.com)

A currency conversion AI agent demonstrating **A2A + ADK + MCP** working together, powered by the [Exchange-RateAPI](https://exchange-rateapi.com) exchange rate API.

It uses the **Agent2Agent (A2A) Python SDK** ([`a2a-sdk`](https://github.com/a2aproject/a2a-python)), Google's **Agent Development Kit** ([`google-adk`](https://github.com/google/adk-python)), and a [FastMCP](https://github.com/jlowin/fastmcp) server that exposes live, historical, and reference exchange rate data from Exchange-RateAPI.

## Overview

```
A2A Client ──▶ A2A Server (ADK Currency Agent, port 10000) ──▶ MCP Server (port 8080) ──▶ Exchange-RateAPI
```

- **MCP Server** — exposes three tools backed by [exchange-rateapi.com](https://exchange-rateapi.com):
  | Tool | Description |
  |---|---|
  | `get_exchange_rate` | Live exchange rate between two currencies, with optional amount conversion |
  | `get_rate_for_date` | Exchange rate on a specific historical date (YYYY-MM-DD) |
  | `list_currencies` | All supported currency codes with full names |
- **ADK Agent** — orchestrates the conversation and invokes the MCP tools when needed.
- **A2A Server/Client** — advertises the agent over the Agent2Agent protocol so other agents can call it.

## Getting Started

### Prerequisites

- Python 3.10+
- A **free Exchange-RateAPI key** — register at [exchange-rateapi.com/register](https://exchange-rateapi.com/register)
- A Google AI Studio API key (for the Gemini model used by the ADK agent)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/Exchange-RateAPI/currency-agent.git
cd currency-agent
```

2. Install [uv](https://docs.astral.sh/uv/getting-started/installation) (used to manage dependencies):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Configure environment variables:

```bash
cp .env.example .env
# then edit .env and set EXCHANGE_RATE_API_KEY and GOOGLE_API_KEY
```

### Run it (three terminals)

**Terminal 1 — MCP server:**

```bash
export $(grep -v '^#' .env | xargs)  # or rely on your shell env
uv run mcp-server/server.py
```

**Terminal 2 — A2A server (ADK agent):**

```bash
uv run uvicorn currency_agent.agent:a2a_app --host localhost --port 10000
```

**Terminal 3 — A2A client:**

```bash
uv run currency_agent/test_client.py
```

You should see the agent answer questions like *"how much is 100 USD in CAD?"* using live Exchange-RateAPI rates.

### Test the MCP server directly

```bash
uv run mcp-server/test_server.py
```

## Use the MCP server with Claude Desktop / Cursor instead

If you just want exchange rate tools in your MCP client (without ADK/A2A), use the production [Exchange-RateAPI MCP server](https://github.com/Exchange-RateAPI/mcp-server):

```json
{
  "mcpServers": {
    "exchange-rateapi": {
      "command": "npx",
      "args": ["-y", "@exchangerateapi/mcp-server"],
      "env": { "EXCHANGE_RATE_API_KEY": "era_live_..." }
    }
  }
}
```

## About Exchange-RateAPI

[Exchange-RateAPI](https://exchange-rateapi.com) is a fast, developer-friendly exchange rate API with live and historical rates, a generous free tier, and official SDKs for [JavaScript](https://github.com/Exchange-RateAPI/exchange-rateapi-js), [Python](https://github.com/Exchange-RateAPI/exchange-rateapi-python), [PHP](https://github.com/Exchange-RateAPI/exchange-rateapi-php), and [Rust](https://github.com/Exchange-RateAPI/exchange-rateapi-rust), plus an [MCP server](https://github.com/Exchange-RateAPI/mcp-server).

## Acknowledgements

Based on the excellent [jackwotherspoon/currency-agent](https://github.com/jackwotherspoon/currency-agent) sample (Apache 2.0), adapted to use Exchange-RateAPI.

## License

[MIT](LICENSE)
