"""Unit tests for the MCP server tools (httpx is mocked — no network calls)."""

import importlib.util
import pathlib
import sys

import pytest

SERVER_PATH = pathlib.Path(__file__).parent.parent / "mcp-server" / "server.py"
spec = importlib.util.spec_from_file_location("server", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
sys.modules["server"] = server
spec.loader.exec_module(server)


def tool_fn(tool):
    """Return the plain function behind a FastMCP tool."""
    return getattr(tool, "fn", tool)


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def env_and_cache(monkeypatch):
    monkeypatch.setenv("EXCHANGE_RATE_API_KEY", "era_test_key")
    server._cache.clear()
    monkeypatch.setattr(server.time, "sleep", lambda s: None)
    yield


def mock_get(monkeypatch, responses):
    """Queue httpx.get responses; records call count and last params."""
    calls = {"count": 0, "params": None}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["count"] += 1
        calls["params"] = params
        item = responses[min(calls["count"] - 1, len(responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(server.httpx, "get", fake_get)
    return calls


def test_get_exchange_rate_passes_amount(monkeypatch):
    calls = mock_get(
        monkeypatch,
        [
            DummyResponse(
                200,
                {
                    "from": {"currency": "USD", "amount": 100},
                    "to": {"currency": "EUR", "amount": 90},
                    "rate": 0.9,
                    "source": "ecb",
                },
            )
        ],
    )
    result = tool_fn(server.get_exchange_rate)("usd", "eur", amount=100)
    assert calls["params"]["amount"] == "100"
    assert calls["params"]["source"] == "USD"
    assert result["rate"] == 0.9


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("EXCHANGE_RATE_API_KEY")
    result = tool_fn(server.get_exchange_rate)("USD", "EUR")
    assert "error" in result and "EXCHANGE_RATE_API_KEY" in result["error"]


def test_retry_then_success(monkeypatch):
    calls = mock_get(
        monkeypatch,
        [DummyResponse(503, {}), DummyResponse(200, {"rate": 1.5, "source": "ecb"})],
    )
    result = tool_fn(server.get_exchange_rate)("USD", "GBP")
    assert result["rate"] == 1.5
    assert calls["count"] == 2


def test_non_retryable_error_surfaces(monkeypatch):
    calls = mock_get(monkeypatch, [DummyResponse(401, {"error": "invalid API key"})])
    result = tool_fn(server.get_exchange_rate)("USD", "EUR")
    assert result == {"error": "API error: invalid API key"}
    assert calls["count"] == 1


def test_cache_hit(monkeypatch):
    calls = mock_get(monkeypatch, [DummyResponse(200, {"rate": 2.0, "source": "ecb"})])
    fn = tool_fn(server.get_exchange_rate)
    fn("USD", "AUD")
    fn("USD", "AUD")
    assert calls["count"] == 1  # second call served from cache


def test_compare_rates_from_list_response(monkeypatch):
    mock_get(
        monkeypatch,
        [
            DummyResponse(
                200,
                [
                    {"rate": 0.9, "source": "USD", "target": "EUR", "time": "t"},
                    {"rate": 0.8, "source": "USD", "target": "GBP", "time": "t"},
                ],
            )
        ],
    )
    result = tool_fn(server.compare_rates)("usd", "eur, gbp")
    assert result == {"base": "USD", "rates": {"EUR": 0.9, "GBP": 0.8}}


def test_get_rate_change(monkeypatch):
    mock_get(
        monkeypatch,
        [
            DummyResponse(
                200,
                [
                    {"date": "2026-06-01", "rate": 1.0},
                    {"date": "2026-06-05", "rate": 0.9},
                ],
            )
        ],
    )
    result = tool_fn(server.get_rate_change)("USD", "EUR", 7)
    assert result["direction"] == "down"
    assert result["change_pct"] == pytest.approx(-10.0)


def test_get_rate_change_bad_days():
    result = tool_fn(server.get_rate_change)("USD", "EUR", 0)
    assert "error" in result


def test_get_rate_for_date_params(monkeypatch):
    calls = mock_get(monkeypatch, [DummyResponse(200, [{"rate": 1.2}])])
    tool_fn(server.get_rate_for_date)("2026-01-15", "USD", "EUR")
    assert calls["params"]["from"] == "2026-01-15"
    assert calls["params"]["to"] == "2026-01-15"
