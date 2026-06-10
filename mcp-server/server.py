import asyncio
import logging
import os

import httpx
from fastmcp import FastMCP

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

API_BASE_URL = os.getenv("EXCHANGE_RATE_API_BASE_URL", "https://exchange-rateapi.com")

mcp = FastMCP("Exchange-RateAPI Currency MCP Server 💶")


def _auth_headers() -> dict[str, str]:
    api_key = os.getenv("EXCHANGE_RATE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "EXCHANGE_RATE_API_KEY is not set. Register for free at "
            "https://exchange-rateapi.com/register to get a key."
        )
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


@mcp.tool()
def get_exchange_rate(
    currency_from: str = "USD",
    currency_to: str = "EUR",
    amount: float | None = None,
):
    """Use this to get the current exchange rate between two currencies.

    Args:
        currency_from: The currency to convert from (e.g., "USD").
        currency_to: The currency to convert to (e.g., "EUR").
        amount: Optional amount to convert (e.g., 1000). If given, the response
            includes the converted amount.

    Returns:
        A dictionary containing the exchange rate data, or an error message if the request fails.
    """
    logger.info(
        f"--- 🛠️ Tool: get_exchange_rate called for converting {currency_from} to {currency_to} ---"
    )
    params: dict[str, str] = {
        "source": currency_from.upper(),
        "target": currency_to.upper(),
    }
    if amount is not None:
        params["amount"] = str(amount)
    try:
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/rates",
            params=params,
            headers=_auth_headers(),
        )
        response.raise_for_status()
        data = response.json()
        logger.info(f"✅ API response: {data}")
        return data
    except httpx.HTTPError as e:
        logger.error(f"❌ API request failed: {e}")
        return {"error": f"API request failed: {e}"}
    except ValueError:
        logger.error("❌ Invalid JSON response from API")
        return {"error": "Invalid JSON response from API."}


@mcp.tool()
def get_rate_for_date(
    date: str,
    currency_from: str = "USD",
    currency_to: str = "EUR",
):
    """Use this to get the exchange rate on a specific historical date.

    Args:
        date: The date in YYYY-MM-DD format (e.g., "2026-01-15").
        currency_from: The currency to convert from (e.g., "USD").
        currency_to: The currency to convert to (e.g., "EUR").

    Returns:
        A dictionary containing the historical exchange rate data, or an error message.
    """
    logger.info(
        f"--- 🛠️ Tool: get_rate_for_date called for {currency_from}/{currency_to} on {date} ---"
    )
    try:
        response = httpx.get(
            f"{API_BASE_URL}/api/historical-rates",
            params={
                "source": currency_from.upper(),
                "target": currency_to.upper(),
                "from": date,
                "to": date,
            },
            headers=_auth_headers(),
        )
        response.raise_for_status()
        data = response.json()
        logger.info(f"✅ API response received for {date}")
        return data
    except httpx.HTTPError as e:
        logger.error(f"❌ API request failed: {e}")
        return {"error": f"API request failed: {e}"}
    except ValueError:
        logger.error("❌ Invalid JSON response from API")
        return {"error": "Invalid JSON response from API."}


@mcp.tool()
def list_currencies():
    """Use this to list all supported currencies.

    Call this when you are unsure whether a currency code is supported, or when
    the user asks which currencies are available.

    Returns:
        A dictionary mapping currency codes to full names
        (e.g., { "USD": "United States Dollar", ... }), or an error message.
    """
    logger.info("--- 🛠️ Tool: list_currencies called ---")
    try:
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/symbols",
            headers=_auth_headers(),
        )
        response.raise_for_status()
        data = response.json()
        logger.info("✅ Symbols returned")
        return data
    except httpx.HTTPError as e:
        logger.error(f"❌ API request failed: {e}")
        return {"error": f"API request failed: {e}"}
    except ValueError:
        logger.error("❌ Invalid JSON response from API")
        return {"error": "Invalid JSON response from API."}


if __name__ == "__main__":
    logger.info(f"🚀 MCP server started on port {os.getenv('PORT', 8080)}")
    # Could also use 'sse' transport, host="0.0.0.0" required for Cloud Run.
    asyncio.run(
        mcp.run_async(
            transport="http",
            host="0.0.0.0",
            port=os.getenv("PORT", 8080),
        )
    )
