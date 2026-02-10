from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.data.providers import TwelveDataProvider
from src.data.providers.twelvedata import _filter_confirmed_bars, _normalize_symbol
from src.data.service import MarketRequest


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.content = b"{}"

    def json(self) -> dict[str, object]:
        return self._payload


def test_normalize_symbol() -> None:
    assert _normalize_symbol("USDJPY") == "USD/JPY"
    assert _normalize_symbol("usd/jpy") == "USD/JPY"
    assert _normalize_symbol("XAUUSD") == "XAU/USD"


def test_filter_confirmed_bars_drops_inflight() -> None:
    now = datetime(2026, 1, 28, 22, 7, tzinfo=timezone.utc)
    bars = [
        {"ts": "2026-01-28T22:00:00Z", "open": 1},
        {"ts": "2026-01-28T22:05:00Z", "open": 2},
    ]
    confirmed = _filter_confirmed_bars(bars, now=now)
    assert [bar["ts"] for bar in confirmed] == ["2026-01-28T22:00:00Z"]


def test_provider_drops_last_bar(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "status": "ok",
        "values": [
            {"datetime": "2026-01-28 22:50:00", "open": "1", "high": "1", "low": "1", "close": "1"},
            {"datetime": "2026-01-28 22:45:00", "open": "1", "high": "1", "low": "1", "close": "1"},
        ],
    }

    def _fake_get(*_args: object, **_kwargs: object) -> _FakeResponse:
        return _FakeResponse(200, payload)

    monkeypatch.setattr("src.data.providers.twelvedata.requests.get", _fake_get)
    provider = TwelveDataProvider(api_key="test", drop_last_bar=True)
    request = MarketRequest(
        symbols=["USDJPY"],
        timeframe="5m",
        start="2026-01-28T22:40:00Z",
        end="2026-01-28T22:50:30Z",
    )
    frames = list(provider.fetch_bars(request))
    assert len(frames) == 1
    assert len(frames[0].bars) == 1
    assert frames[0].bars[0]["ts"] == "2026-01-28T22:45:00Z"


def test_provider_requests_utc_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    payload = {"status": "ok", "values": []}

    def _fake_get(*_args: object, **kwargs: object) -> _FakeResponse:
        captured.update(kwargs)
        return _FakeResponse(200, payload)

    monkeypatch.setattr("src.data.providers.twelvedata.requests.get", _fake_get)
    provider = TwelveDataProvider(api_key="test", drop_last_bar=True)
    request = MarketRequest(
        symbols=["USDJPY"],
        timeframe="5m",
        start="2026-01-28T22:40:00Z",
        end="2026-01-28T22:50:30Z",
    )
    list(provider.fetch_bars(request))

    params = captured.get("params")
    assert isinstance(params, dict)
    assert params.get("timezone") == "UTC"
