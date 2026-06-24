from __future__ import annotations

import pytest
import requests

from scrapers import http_client
from scrapers.http_client import CircuitOpenError, HttpClient, RobotsDisallowedError


class FakeResponse:
    def __init__(self, status_code: int = 200, headers: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
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


# -- Phase 3: politeness hardening -----------------------------------------


class RoutingSession:
    """Fake session that serves robots.txt and routes other URLs to responses."""

    def __init__(self, routes: dict, robots_text: str | None = None) -> None:
        self.routes = routes
        self.robots_text = robots_text
        self.calls: list[dict] = []
        self.headers: dict = {}

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if url.endswith("/robots.txt"):
            return FakeResponse(200, text=self.robots_text) if self.robots_text is not None else FakeResponse(404)
        result = self.routes.get(url)
        if result is None:
            return FakeResponse(404)
        if isinstance(result, Exception):
            raise result
        return result


def test_robots_txt_blocks_disallowed_path_but_allows_others(monkeypatch):
    monkeypatch.setattr(http_client.time, "sleep", lambda *_: None)
    session = RoutingSession(
        routes={"https://x.com/public": FakeResponse(200)},
        robots_text="User-agent: *\nDisallow: /private\n",
    )
    client = HttpClient(rate_limit_seconds=0, jitter_seconds=0, session=session, respect_robots=True)

    assert client.get("https://x.com/public").status_code == 200
    with pytest.raises(RobotsDisallowedError):
        client.get("https://x.com/private/secret")


def test_bypass_robots_allows_disallowed_api_url(monkeypatch):
    monkeypatch.setattr(http_client.time, "sleep", lambda *_: None)
    session = RoutingSession(
        routes={"https://api.example.com/search.json": FakeResponse(200)},
        robots_text="User-agent: *\nDisallow: /search.json\n",
    )
    client = HttpClient(rate_limit_seconds=0, jitter_seconds=0, session=session, respect_robots=True)

    # Without bypass this path is disallowed; with bypass (a documented API) it goes through.
    with pytest.raises(RobotsDisallowedError):
        client.get("https://api.example.com/search.json")
    assert client.get("https://api.example.com/search.json", bypass_robots=True).status_code == 200


def test_conditional_caching_reuses_response_on_304(monkeypatch):
    monkeypatch.setattr(http_client.time, "sleep", lambda *_: None)
    first = FakeResponse(200, headers={"ETag": "abc123"})
    session = FakeSession([first, FakeResponse(304)])
    client = HttpClient(rate_limit_seconds=0, jitter_seconds=0, session=session, respect_robots=False, enable_cache=True)

    r1 = client.get("https://api.example.com/data")
    r2 = client.get("https://api.example.com/data")

    assert r1 is first
    assert r2 is first  # the cached body is reused on 304 Not Modified
    assert session.calls[1]["headers"].get("If-None-Match") == "abc123"


class AlwaysSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict] = []
        self.headers: dict = {}

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


def test_circuit_breaker_opens_after_threshold(monkeypatch):
    monkeypatch.setattr(http_client.time, "sleep", lambda *_: None)
    session = AlwaysSession(FakeResponse(500))
    client = HttpClient(
        rate_limit_seconds=0,
        jitter_seconds=0,
        session=session,
        respect_robots=False,
        max_retries=0,
        circuit_breaker_threshold=2,
    )

    for _ in range(2):
        with pytest.raises(requests.HTTPError):
            client.get("https://flaky.example.com/x")

    calls_before = len(session.calls)
    with pytest.raises(CircuitOpenError):
        client.get("https://flaky.example.com/x")  # short-circuits, no network call
    assert len(session.calls) == calls_before
