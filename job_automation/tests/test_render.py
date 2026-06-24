from __future__ import annotations

import sys
import types

import pytest

import config
from scrapers.render import PlaywrightNotAvailable, render_html


def test_render_disabled_raises(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_PLAYWRIGHT", False)
    with pytest.raises(PlaywrightNotAvailable):
        render_html("https://example.com")


# -- a minimal fake of playwright.sync_api ---------------------------------


class _FakePage:
    def __init__(self, html: str) -> None:
        self._html = html
        self.goto_args = None
        self.user_agent = None

    def goto(self, url, **kwargs):
        self.goto_args = (url, kwargs)

    def content(self):
        return self._html


class _FakeBrowser:
    def __init__(self, html: str) -> None:
        self.page = _FakePage(html)
        self.closed = False

    def new_page(self, **kwargs):
        self.page.user_agent = kwargs.get("user_agent")
        return self.page

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, html: str) -> None:
        self.html = html
        self.launch_kwargs = None
        self.browser = None

    def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        self.browser = _FakeBrowser(self.html)
        return self.browser


class _FakePlaywright:
    def __init__(self, html: str) -> None:
        self.chromium = _FakeChromium(html)


class _FakeCtx:
    def __init__(self, html: str) -> None:
        self.player = _FakePlaywright(html)

    def __enter__(self):
        return self.player

    def __exit__(self, *exc):
        return False


def _install_fake_playwright(monkeypatch, html: str) -> None:
    module = types.ModuleType("playwright.sync_api")
    module.sync_playwright = lambda: _FakeCtx(html)
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", module)


def test_render_enabled_returns_rendered_html(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_PLAYWRIGHT", True)
    monkeypatch.setattr(config, "HEADLESS_BROWSER", True)
    _install_fake_playwright(monkeypatch, "<html><body>RENDERED CONTENT</body></html>")

    html = render_html("https://spa.example.com/jobs")

    assert "RENDERED CONTENT" in html
