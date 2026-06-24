from __future__ import annotations

import requests

from scrapers import http_client
from scrapers.http_client import HttpClient


class FakeResponse:
    def __init__(self, status_code: int = 200, headers: dict | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.url = "https://example.com"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class FakeSession:
    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.headers: dict = {}

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _client(session: FakeSession, monkeypatch, **kwargs) -> HttpClient:
    # Never actually sleep during tests.
    monkeypatch.setattr(http_client.time, "sleep", lambda *_: None)
    return HttpClient(rate_limit_seconds=0, jitter_seconds=0, session=session, **kwargs)


def test_get_returns_successful_response_and_sets_user_agent(monkeypatch):
    session = FakeSession([FakeResponse(200)])
    client = _client(session, monkeypatch)

    response = client.get("https://example.com/api")

    assert response.status_code == 200
    assert len(session.calls) == 1
    assert "User-Agent" in session.calls[0]["headers"]


def test_get_retries_on_transient_status_then_succeeds(monkeypatch):
    session = FakeSession([FakeResponse(503), FakeResponse(503), FakeResponse(200)])
    client = _client(session, monkeypatch, max_retries=3)

    response = client.get("https://example.com/api")

    assert response.status_code == 200
    assert len(session.calls) == 3  # two retries + success


def test_get_retries_on_request_exception_then_succeeds(monkeypatch):
    session = FakeSession([requests.ConnectionError("boom"), FakeResponse(200)])
    client = _client(session, monkeypatch, max_retries=2)

    response = client.get("https://example.com/api")

    assert response.status_code == 200
    assert len(session.calls) == 2


def test_get_raises_after_exhausting_retries(monkeypatch):
    session = FakeSession([FakeResponse(503), FakeResponse(503)])
    client = _client(session, monkeypatch, max_retries=1)

    try:
        client.get("https://example.com/api")
    except requests.HTTPError:
        pass
    else:  # pragma: no cover - the call must raise
        raise AssertionError("expected HTTPError after retries are exhausted")

    assert len(session.calls) == 2  # initial + one retry, then raise_for_status


def test_retry_after_header_is_honored(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(http_client.time, "sleep", lambda seconds: sleeps.append(seconds))
    session = FakeSession([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200)])
    client = HttpClient(rate_limit_seconds=0, jitter_seconds=0, session=session, max_retries=2)

    client.get("https://example.com/api")

    assert any(value >= 7 for value in sleeps)
