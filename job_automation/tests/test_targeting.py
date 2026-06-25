from __future__ import annotations

from matching import targeting


def test_get_list_falls_back_to_default_when_missing(monkeypatch):
    monkeypatch.setattr(targeting, "_DATA", {})
    assert targeting.get_list("target_titles", ["ai engineer"]) == ["ai engineer"]


def test_get_list_uses_yaml_value_and_lowercases(monkeypatch):
    monkeypatch.setattr(targeting, "_DATA", {"target_titles": ["AI Automation Specialist", " n8n Builder "]})
    assert targeting.get_list("target_titles", ["fallback"]) == ["ai automation specialist", "n8n builder"]


def test_get_list_can_preserve_case(monkeypatch):
    monkeypatch.setattr(targeting, "_DATA", {"search_sites": ["site:Join.com"]})
    assert targeting.get_list("search_sites", [], lower=False) == ["site:Join.com"]


def test_get_list_ignores_empty_or_non_list(monkeypatch):
    monkeypatch.setattr(targeting, "_DATA", {"target_titles": [], "off_target_title_signals": "nope"})
    assert targeting.get_list("target_titles", ["d"]) == ["d"]
    assert targeting.get_list("off_target_title_signals", ["d"]) == ["d"]


def test_get_region_terms_override_and_fallback(monkeypatch):
    default = {"europe": ["Europe"]}
    monkeypatch.setattr(targeting, "_DATA", {"region_terms": {"DACH": ["Germany", "Austria"]}})
    assert targeting.get_region_terms(default) == {"dach": ["Germany", "Austria"]}

    monkeypatch.setattr(targeting, "_DATA", {})
    assert targeting.get_region_terms(default) == default
