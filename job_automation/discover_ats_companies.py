from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
import typer
import yaml
from rich.console import Console

from config import COMPANIES_FILE, SERPAPI_API_KEY, SERPAPI_CAPTURE_DIR
from scrapers.ats_scraper import load_companies


app = typer.Typer(help="Discover ATS company slugs via SerpAPI and merge them into companies.yaml.")
console = Console()


# One query per (ATS site, keyword) finds many company boards at once -- this is
# the frugal way to use SerpAPI: discover companies, then fetch their jobs for free
# via the ATS scraper. See SCRAPER_ROADMAP.md, Phase 4.
ATS_SITES = {
    "greenhouse": "boards.greenhouse.io",
    "lever": "jobs.lever.co",
    "ashby": "jobs.ashbyhq.com",
    "workable": "apply.workable.com",
}
DISCOVERY_KEYWORDS = ["AI engineer", "AI automation", "machine learning engineer"]

# Path segments that are never a company slug.
SLUG_STOPWORDS = {"embed", "job_board", "j", "jobs", "o", "api", "v1", "v0", ""}


def build_queries() -> list[str]:
    """All site/keyword discovery queries, ordered so a small --limit still spans ATSs."""
    queries: list[str] = []
    for keyword in DISCOVERY_KEYWORDS:
        for site in ATS_SITES.values():
            queries.append(f'site:{site} "{keyword}"')
    return queries


def extract_slug(url: str) -> tuple[str, str] | None:
    """Return (provider, slug) for an ATS board URL, or None if it is not one."""
    parts = urlparse(url)
    host = parts.netloc.lower().removeprefix("www.")
    segments = [segment for segment in parts.path.split("/") if segment]

    if "greenhouse.io" in host:
        for_slug = parse_qs(parts.query).get("for", [None])[0]
        if _valid_slug(for_slug):
            return "greenhouse", for_slug
        slug = _first_real_segment(segments, skip={"embed", "job_board"})
        return ("greenhouse", slug) if slug else None
    if "lever.co" in host:
        return ("lever", segments[0]) if segments and _valid_slug(segments[0]) else None
    if "ashbyhq.com" in host:
        return ("ashby", segments[0]) if segments and _valid_slug(segments[0]) else None
    if "workable.com" in host:
        subdomain = host.split(".")[0]
        if host.endswith(".workable.com") and subdomain not in {"apply", "www"} and _valid_slug(subdomain):
            return "workable", subdomain
        slug = _first_real_segment(segments, skip=set())
        return ("workable", slug) if slug else None
    return None


def _valid_slug(segment: str | None) -> bool:
    """A real ATS slug: no encoded spaces (%20), punctuation noise, or stopwords."""
    if not segment or segment in SLUG_STOPWORDS:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", segment))


def _first_real_segment(segments: list[str], skip: set[str]) -> str | None:
    for segment in segments:
        if segment in SLUG_STOPWORDS or segment in skip:
            continue
        return segment if _valid_slug(segment) else None
    return None


def extract_slugs(results: list[dict]) -> dict[str, set[str]]:
    """Collect provider -> set(slugs) from a list of SerpAPI organic results."""
    found: dict[str, set[str]] = {provider: set() for provider in ATS_SITES}
    for result in results:
        link = str(result.get("link") or "")
        parsed = extract_slug(link)
        if parsed:
            provider, slug = parsed
            found.setdefault(provider, set()).add(slug.strip().lower())
    return found


def merge_into_companies(path: Path, found: dict[str, set[str]]) -> dict[str, list[str]]:
    """Merge discovered slugs into companies.yaml, return the new counts added."""
    existing = load_companies(path)
    added: dict[str, list[str]] = {}
    merged: dict[str, list[str]] = {}
    for provider in ATS_SITES:
        current = set(existing.get(provider, []))
        discovered = found.get(provider, set())
        new = sorted(discovered - current)
        added[provider] = new
        merged[provider] = sorted(current | discovered)
    _write_companies(path, merged)
    return added


def _write_companies(path: Path, companies: dict[str, list[str]]) -> None:
    lines = ["# Target company ATS slugs for the key-free ATS scraper (--sources ats).",
             "# Auto-managed by discover_ats_companies.py; you can also edit by hand.", ""]
    for provider in ("greenhouse", "lever", "ashby", "workable"):
        lines.append(f"{provider}:")
        for slug in companies.get(provider, []):
            lines.append(f"  - {slug}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _serpapi_search(query: str) -> list[dict]:
    response = requests.get(
        "https://serpapi.com/search.json",
        params={"engine": "google", "q": query, "api_key": SERPAPI_API_KEY},
        timeout=30,
    )
    data = response.json()
    if SERPAPI_CAPTURE_DIR:
        capture_dir = Path(SERPAPI_CAPTURE_DIR)
        capture_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:60]
        (capture_dir / f"discovery_{safe}.json").write_text(
            json.dumps({"query": query, "data": data}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return data.get("organic_results", []) or []


@app.command()
def main(
    limit: int = typer.Option(5, help="Max SerpAPI queries to run (each costs one credit). Hard-capped at 5."),
    output: Path | None = typer.Option(None, help="companies.yaml path (defaults to project file)."),
) -> None:
    if not SERPAPI_API_KEY:
        console.print("[red]No SERPAPI_API_KEY set. Cannot run discovery.[/]")
        raise typer.Exit(code=1)

    # SerpAPI credits are scarce; never spend more than 5 in a single discovery run.
    SERPAPI_SEARCH_CAP = 5
    if limit > SERPAPI_SEARCH_CAP:
        console.print(f"[yellow]Capping discovery to {SERPAPI_SEARCH_CAP} SerpAPI searches (requested {limit}).[/]")
        limit = SERPAPI_SEARCH_CAP
    queries = build_queries()[:limit]
    console.print(f"Running {len(queries)} discovery queries (of {len(build_queries())} possible)...")
    all_found: dict[str, set[str]] = {provider: set() for provider in ATS_SITES}
    for index, query in enumerate(queries, start=1):
        try:
            results = _serpapi_search(query)
        except Exception as error:  # noqa: BLE001
            console.print(f"[yellow]query {index} failed:[/] {error}")
            continue
        for provider, slugs in extract_slugs(results).items():
            all_found[provider] |= slugs
        console.print(f"  [{index}/{len(queries)}] {query} -> {sum(len(s) for s in extract_slugs(results).values())} slugs")
        time.sleep(1)

    added = merge_into_companies(output or COMPANIES_FILE, all_found)
    total_added = sum(len(v) for v in added.values())
    console.print(f"\nDiscovered slugs: " + ", ".join(f"{p}={len(s)}" for p, s in all_found.items()))
    console.print(f"Newly added to companies.yaml: {total_added} " + ", ".join(f"{p}+{len(v)}" for p, v in added.items()))


if __name__ == "__main__":
    app()
