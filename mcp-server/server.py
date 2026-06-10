import asyncio
import logging
import os
import time
from datetime import date, timedelta

import httpx
from fastmcp import FastMCP

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

API_BASE_URL = os.getenv("EXCHANGE_RATE_API_BASE_URL", "https://exchange-rateapi.com")
REQUEST_TIMEOUT = 10.0
MAX_RETRIES = 3
RETRYABLE_STATUS = (429, 500, 502, 503, 504)
RATE_TTL = 300  # seconds — live rates are cached briefly to save API quota
SYMBOLS_TTL = 86400  # the currency list rarely changes

mcp = FastMCP("Exchange-RateAPI Currency MCP Server 💶")

_cache: dict[str, tuple[float, dict | list]] = {}


def _cache_get(key: str):
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    return None


def _cache_set(key: str, value, ttl: float) -> None:
    _cache[key] = (time.time() + ttl, value)


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict) and isinstance(body.get("error"), str):
            return body["error"]
    except ValueError:
        pass
    return f"HTTP {response.status_code}"


def api_get(path: str, params: dict | None = None, *, ttl: float = RATE_TTL):
    """GET from Exchange-RateAPI with caching, timeout, and retries.

    Returns the parsed JSON on success, or {"error": "..."} on failure.
    """
    api_key = os.getenv("EXCHANGE_RATE_API_KEY")
    if not api_key:
        return {
            "error": (
                "EXCHANGE_RATE_API_KEY is not set. Register for free at "
                "https://exchange-rateapi.com/register to get a key."
            )
        }

    params = params or {}
    cache_key = f"{path}?{sorted(params.items())}"
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info(f"💾 Cache hit for {path}")
        return cached

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    last_error = "unknown error"
    for attempt in range(MAX_RETRIES):
        if attempt:
            time.sleep(0.5 * 2 ** (attempt - 1))
        try:
            response = httpx.get(
                f"{API_BASE_URL}{path}",
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as e:
            last_error = f"request failed: {e}"
            logger.warning(f"⚠️ Attempt {attempt + 1}/{MAX_RETRIES} {last_error}")
            continue

        if response.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES - 1:
            last_error = _error_detail(response)
            logger.warning(f"⚠️ Attempt {attempt + 1}/{MAX_RETRIES} got {last_error}, retrying")
            continue

        if response.status_code >= 400:
            return {"error": f"API error: {_error_detail(response)}"}

        try:
            data = response.json()
        except ValueError:
            return {"error": "Invalid JSON response from API."}
        _cache_set(cache_key, data, ttl)
        return data

    return {"error": f"API request failed after {MAX_RETRIES} attempts ({last_error})."}


@mcp.tool()
def get_exchange_rate(
    currency_from: str = "USD",
    currency_to: str = "EUR",
    amount: float | None = None,
):
    """Use this to get the current exchange rate between two currencies, and
    optionally convert an amount.

    Args:
        currency_from: The currency to convert from (e.g., "USD").
        currency_to: The currency to convert to (e.g., "EUR").
        amount: Optional amount to convert (e.g., 1000). If given, the response
            includes the converted amount — prefer this over doing the
            multiplication yourself.

    Returns:
        A dictionary containing the exchange rate data, or an error message if
        the request fails.
    """
    source, target = currency_from.upper(), currency_to.upper()
    logger.info(f"--- 🛠️ Tool: get_exchange_rate {source} → {target} (amount={amount}) ---")
    params: dict[str, str] = {"source": source, "target": target}
    if amount is not None:
        params["amount"] = str(amount)
    return api_get("/api/v1/rates", params)


@mcp.tool()
def compare_rates(
    currency_from: str = "USD",
    currency_to_list: str = "EUR,GBP,JPY",
):
    """Use this to compare one base currency against several target currencies
    at once.

    Args:
        currency_from: The base currency (e.g., "USD").
        currency_to_list: Comma-separated target currency codes (e.g.,
            "EUR,GBP,JPY"). Maximum 10 targets.

    Returns:
        A dictionary with { base, rates: { CODE: rate, ... } }, or an error message.
    """
    source = currency_from.upper()
    targets = [t.strip().upper() for t in currency_to_list.split(",") if t.strip()][:10]
    logger.info(f"--- 🛠️ Tool: compare_rates {source} vs {targets} ---")
    data = api_get("/api/v1/rates", {"source": source, "target": ",".join(targets)})
    if isinstance(data, dict) and "error" in data:
        return data
    entries = data if isinstance(data, list) else [data]
    rates: dict[str, float] = {}
    for entry in entries:
        if isinstance(entry, dict) and "target" in entry and "rate" in entry:
            rates[entry["target"]] = entry["rate"]
    if not rates:
        return {"error": "Unexpected API response format.", "raw": data}
    return {"base": source, "rates": rates}


@mcp.tool()
def get_rate_for_date(
    date_str: str,
    currency_from: str = "USD",
    currency_to: str = "EUR",
):
    """Use this to get the exchange rate on a specific historical date.

    Args:
        date_str: The date in YYYY-MM-DD format (e.g., "2026-01-15").
        currency_from: The currency to convert from (e.g., "USD").
        currency_to: The currency to convert to (e.g., "EUR").

    Returns:
        A dictionary containing the historical exchange rate data, or an error message.
    """
    source, target = currency_from.upper(), currency_to.upper()
    logger.info(f"--- 🛠️ Tool: get_rate_for_date {source}/{target} on {date_str} ---")
    return api_get(
        "/api/historical-rates",
        {"source": source, "target": target, "from": date_str, "to": date_str},
    )


@mcp.tool()
def get_rate_change(
    currency_from: str = "USD",
    currency_to: str = "EUR",
    days: int = 7,
):
    """Use this to find out how an exchange rate has moved over the last N days —
    e.g. to answer "is EUR up or down against USD this week?".

    Args:
        currency_from: The currency to convert from (e.g., "USD").
        currency_to: The currency to convert to (e.g., "EUR").
        days: Lookback window in days (1–365). Defaults to 7.

    Returns:
        A dictionary with start/end rates, absolute and percent change, and
        direction ("up", "down" or "flat"), or an error message.
    """
    source, target = currency_from.upper(), currency_to.upper()
    logger.info(f"--- 🛠️ Tool: get_rate_change {source}/{target} over {days}d ---")
    if not 1 <= days <= 365:
        return {"error": "days must be between 1 and 365."}
    today = date.today()
    start = today - timedelta(days=days)
    data = api_get(
        "/api/historical-rates",
        {
            "source": source,
            "target": target,
            "from": start.isoformat(),
            "to": today.isoformat(),
        },
    )
    if isinstance(data, dict) and "error" in data:
        return data
    # Normalise: accept either a list of points or a dict wrapping one
    points = data if isinstance(data, list) else data.get("data") or data.get("rates") or []
    if not isinstance(points, list) or len(points) < 2:
        return {"error": f"Not enough data points for {source}/{target} over {days} days."}
    first, last = points[0], points[-1]
    start_rate = first.get("rate") if isinstance(first, dict) else None
    end_rate = last.get("rate") if isinstance(last, dict) else None
    if not isinstance(start_rate, (int, float)) or not isinstance(end_rate, (int, float)):
        return {"error": "Unexpected data format in historical rates."}
    change = end_rate - start_rate
    change_pct = (change / start_rate * 100) if start_rate else 0.0
    return {
        "from": source,
        "to": target,
        "days": days,
        "start_date": first.get("date") or first.get("time"),
        "start_rate": start_rate,
        "end_date": last.get("date") or last.get("time"),
        "end_rate": end_rate,
        "change": round(change, 6),
        "change_pct": round(change_pct, 4),
        "direction": "up" if change > 0 else "down" if change < 0 else "flat",
    }


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
    return api_get("/api/v1/symbols", ttl=SYMBOLS_TTL)


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
