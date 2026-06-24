# Scraper Roadmap — making the own crawler strong (and SerpAPI optional)

> Goal: be able to **switch between SerpAPI and a self-built crawler**, and make the self-built one
> reliable, high-quality, and low-risk to run — *without* getting IP-blacklisted.
>
> This document is the plan. It is intentionally opinionated about **how** to be "strong", because the
> intuitive answer ("evade detection") is the weak one. Read section 1 first.

---

## 1. The honest framing: "strong" ≠ "evasive"

It is tempting to think a powerful scraper is one that disguises itself and beats anti-bot systems.
In practice that approach is **fragile, high-maintenance, and risky**, and it is *not* what robust
job-data pipelines actually do. Here is the reality:

- Sites like **LinkedIn, Indeed, Glassdoor** run commercial anti-bot systems (Cloudflare, DataDome,
  PerimeterX). Defeating them means CAPTCHA-solving, browser-fingerprint spoofing, and residential
  proxy rotation. That is an arms race you lose over time, it usually **violates their Terms of
  Service**, it can carry **legal risk**, and it gets your IP/account banned anyway. This project
  already lists those domains in `blocked_domains` and will keep avoiding them.
- The genuinely strong move is to **get structured data from sources that want to be read by
  machines.** A surprising amount of the job market is available this way, cleanly and legally.

So this roadmap optimizes for **coverage + reliability + politeness**, not stealth. The result is a
crawler that returns better jobs than the SerpAPI path, rarely gets blocked, and needs little babysitting.

**What this plan will NOT include:** CAPTCHA solving, fingerprint/TLS spoofing to bypass anti-bot
walls, scraping behind logins, or ignoring `robots.txt`. If a source requires those, the right answer
is "use its API, its feed, or skip it."

---

## 2. The real unlock: ATS APIs and public feeds (no key, no scraping)

Most startups and small companies (exactly the **< 200-employee** targets of this project) host their
jobs on a handful of **Applicant Tracking Systems** that expose **public JSON endpoints meant for
consumption**. No API key, no scraping, no blocking:

| ATS | Public endpoint shape | Notes |
|---|---|---|
| **Greenhouse** | `https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true` | Clean JSON, full descriptions, locations. |
| **Lever** | `https://api.lever.co/v0/postings/{company}?mode=json` | JSON list with text + categories. |
| **Ashby** | `https://api.ashbyhq.com/posting-api/job-board/{company}` | JSON job board. |
| **Workable** | `https://apply.workable.com/api/v3/accounts/{company}/jobs` | JSON, supports paging. |
| **Recruitee** | `https://{company}.recruitee.com/api/offers/` | JSON offers. |
| **SmartRecruiters** | `https://api.smartrecruiters.com/v1/companies/{company}/postings` | JSON postings. |
| **Personio** | `https://{company}.jobs.personio.de/xml` | XML feed (popular in DACH). |

**Why this is the centerpiece:** these return well-structured fields (title, location, description,
department, sometimes salary) that map almost 1:1 onto our `Job` model, with **zero anti-bot risk**.
The only thing needed is a **list of company slugs** to query. That list can come from:

- a curated `companies.yaml` you maintain (your real targets),
- the YC / Wellfound / startup directories (one-time slug harvest),
- the current `generic` SerpAPI results (use SerpAPI sparingly just to *discover* slugs, then hit the
  ATS APIs for free forever after).

This single addition would do more for quality than any stealth technique.

Complementary key-free feeds already partly used or easy to add: **RemoteOK**, **Remotive**,
**Arbeitnow** (already in), plus **WeWorkRemotely RSS** (`/remote-jobs.rss`), **Hacker News
"Who is hiring"** (Algolia API), **Himalayas**, **jobicy** RSS, and company **sitemaps**.

---

## 3. Polite-client infrastructure (this is what actually prevents blocks)

For the HTML/feed fetching that remains, "being a good citizen" prevents far more blocks than any
disguise. Build a shared HTTP layer used by every scraper:

1. **robots.txt compliance** — fetch and cache each host's `robots.txt`; skip disallowed paths.
   (`urllib.robotparser` or `protego`.)
2. **Rate limiting per host + jitter** — keep the existing `SCRAPER_RATE_LIMIT_SECONDS` but make it
   **per-domain** and add random jitter (e.g. 1.5–4s) so traffic looks human-paced, not robotic.
3. **Exponential backoff with retries** — on `429`/`503`/timeouts, back off and retry a few times,
   then give up gracefully. (`tenacity`.) Honor `Retry-After` headers.
4. **HTTP caching / conditional requests** — store `ETag`/`Last-Modified` and send
   `If-None-Modified`; cache responses so re-runs don't refetch unchanged pages. (`hishel` or
   `requests-cache`.) This alone massively cuts request volume.
5. **Realistic, rotating headers** — a small pool of current, *real* browser `User-Agent` strings plus
   matching `Accept`/`Accept-Language`. This is normal courtesy, not spoofing an anti-bot system.
6. **Session reuse + connection pooling** — one `httpx`/`requests` session per host.
7. **Concurrency caps** — small bounded concurrency (e.g. 4–8) with per-host limits; never hammer.
8. **Optional proxy support** — a pluggable proxy/rotation hook for *legitimate* distributed load or
   geo-located queries. Off by default. (Not a tool to bypass bans — if a site bans you, stop.)
9. **Circuit breaker** — if a host returns repeated 403/429, mark it cooling-off and skip for the run.

These map onto the existing `BaseScraper.get()` / `respect_rate_limit()` / `handle_errors()` hooks, so
this is an upgrade of infrastructure already present, not a rewrite.

---

## 4. Recommended libraries

| Need | Library | Why |
|---|---|---|
| HTTP client | **httpx** | HTTP/2, async, timeouts, proxies; drop-in for `requests`. |
| Retries/backoff | **tenacity** | Declarative retry with jittered exponential backoff. |
| HTTP caching | **hishel** (or `requests-cache`) | RFC-compliant caching / conditional requests. |
| Fast HTML parsing | **selectolax** (keep `lxml`/`bs4`) | 5–10× faster CSS parsing for big pages. |
| RSS/Atom | **feedparser** | Robust feed parsing. |
| Sitemaps | **ultimate-sitemap-parser** / `advertools` | Enumerate job URLs from sitemaps. |
| robots.txt | **protego** (or stdlib) | Accurate `robots.txt` evaluation. |
| JS-rendered *allowed* sites | **Playwright** (already a dep) | Only where a site's own ToS permits and no API exists. |
| Content extraction | **trafilatura** | Clean main-text extraction from arbitrary job pages. |

`curl_cffi` (TLS-impersonation) is deliberately **left out** — it exists to defeat fingerprinting,
which is exactly the line this project does not cross.

---

## 5. The SerpAPI ⇄ own-scraper switch

Make the backend explicit instead of "whatever key is set":

- Add `SEARCH_BACKEND=serpapi|crawler|auto` to `.env` / `config.py` (default `auto`:
  use SerpAPI if a key exists, else the crawler).
- Keep `generic` = SerpAPI (unchanged), and introduce a new source key, e.g. `crawler`, that runs the
  key-free ATS/feed/sitemap engine from sections 2–3.
- Both produce the same `Job` objects and flow through the same dedup/scoring/export pipeline, so they
  are fully interchangeable and can even run together (`--sources crawler,remoteok,remotive`).

Use SerpAPI for what it's uniquely good at — **discovery** of new companies/boards — then let the free
crawler do the heavy, repeatable fetching against ATS APIs.

---

## 6. Phased plan

**Phase 0 — groundwork (small, no behaviour change)** — ✅ **done**
- Shared `scrapers/http_client.py` (`requests`-based: per-host rate limit + jitter, retry/backoff
  honoring `Retry-After`, rotating honest UA pool) now backs `BaseScraper.get()`.
- `SEARCH_BACKEND`, `HTTP_MAX_RETRIES`, `HTTP_JITTER_SECONDS`, and `COMPANIES_FILE` added to config.
- Note: implemented on `requests` to avoid new install friction; swapping to `httpx`/`tenacity`/
  `hishel` later is a drop-in because everything goes through one client. (robots.txt + HTTP caching
  were added in Phase 3.)

**Phase 1 — ATS engine (biggest win)** — ✅ **done (Greenhouse + Lever + Ashby + Workable)**
- `scrapers/ats_scraper.py` fetches all four ATS public JSON boards, keeps AI/automation-relevant
  titles, maps to `Job`, and runs the normal enrichment. Slugs come from `companies.yaml`.
- Registered as `--sources ats`. Offline fixture tests in `tests/test_ats_scraper.py`.
- Workable was also live-validated against real boards (Hugging Face, Skroutz); the live review fixed
  remote detection to use Workable's actual `telecommuting` field.
- **TODO:** seed `companies.yaml` with your real targets.

**Phase 2 — feeds & sitemaps** — ✅ **done (sitemaps deprioritized)**
- We Work Remotely now uses its public RSS feed (`/remote-jobs.rss`) instead of the 403 HTML search
  (`scrapers/weworkremotely_scraper.py`).
- Hacker News "Ask HN: Who is hiring?" via the Algolia API (`scrapers/hackernews_scraper.py`,
  `--sources hackernews`): finds the latest monthly thread, parses each top-level comment into a
  company/role/location/remote posting, and keeps only AI/automation-relevant ones. A live review
  yielded ~40 AI-startup postings per month.
- Generic RSS/Atom scraper (`scrapers/rss_scraper.py`, `--sources rss`): reads a configurable feed
  list (`RSS_FEEDS`, defaults to Himalayas + WeWorkRemotely categories + Jobspresso). A live review
  fixed company extraction (explicit `<company>`/`<companyName>`/`<dc:creator>` tag, else "Company: Role"),
  switched to title-based relevance (full descriptions were too noisy), guarded the German ":in" gender
  form, and dropped bare "agent" from the AI signals (it matched human "Customer Service Agent" roles).
- Broad feeds (RemoteOK, Arbeitnow, RSS) run a shared relevance pre-filter (`matching/relevance.py`)
  so the per-source budget is spent on AI/automation roles, and a text sanitizer
  (`base_scraper.clean_field`) strips upstream-corrupted characters.
- Sitemap enumeration is intentionally deprioritized: it is brittle and per-site, and the ATS APIs
  already provide structured per-company job data far more reliably.

**Phase 3 — politeness hardening** — ✅ **done**
- Shared HTTP client now adds, on top of per-host limiter + jitter + backoff + UA pool:
  robots.txt enforcement (disallowed URLs raise `RobotsDisallowedError`), conditional-request caching
  (ETag / Last-Modified → `304` reuse), and a per-host circuit breaker (`CircuitOpenError` after N
  consecutive failures). Knobs: `HTTP_RESPECT_ROBOTS`, `HTTP_ENABLE_CACHE`, `HTTP_CIRCUIT_BREAKER_THRESHOLD`.
- Verified all real sources are allowed by their robots.txt; live HN run unaffected. Offline tests in
  `tests/test_http_client.py`.
- Future option: persist the HTTP cache across runs (currently in-memory per run).

**Phase 4 — discovery loop** — ✅ **done**
- `discover_ats_companies.py` (`python discover_ats_companies.py --limit 12`) spends a *small* SerpAPI
  budget on `site:<ats>.<domain> "<keyword>"` queries to discover ATS company slugs, then merges them
  into `companies.yaml` so the free ATS scraper fetches their jobs forever. This is how you stop paying
  SerpAPI over time.
- Budget allocation: 4 ATS domains × 3 keywords = 12 queries. A live run found ~114 company slugs from
  12 credits; raw responses are captured (`SERPAPI_CAPTURE_DIR`) so slug extraction can be re-tuned
  offline for free. Offline tests in `tests/test_discover.py`.
- **Caveat:** discovery cannot know company size, so the list mixes small startups with large companies
  (Reddit, Lyft, Palantir, …). Prune `companies.yaml` by hand, or rely on the <200-employee filter where
  size is detectable and on scoring/`--min-score` to push senior/large-company roles down.

**Phase 5 — optional JS rendering**
- Only for sources whose ToS allows it and which have no API/feed, via Playwright, rate-limited.

Each phase is independently shippable and testable offline (monkeypatched HTTP + saved fixtures), the
same pattern as `test_serpapi_quality_pipeline.py`.

**SerpAPI scraper hardening (done, supports the discovery loop).** Reviewing a real 10-query capture
exposed parsing gaps; the `generic` scraper now blocks dictionary/movie/streaming domains (single words
like "junior" matched them), extracts companies from English "at", German "bei" and "@", returns
`Unknown` for aggregator boards, and rejects numeric job ids, call-to-action phrases, departments and
place names as company names. `SERPAPI_CAPTURE_DIR` saves raw responses so this kind of tuning happens
offline without spending credits (`SERPAPI_FETCH_DETAILS=false` makes capture runs fast).

---

## 7. Definition of "strong" for this project

A strong crawler here means:

- **High-quality jobs**: structured ATS data + good noise filtering beats scraping search snippets.
- **Reliable**: caching + retries + robots compliance → it just keeps working across runs.
- **Cheap**: free ATS/feed sources; SerpAPI only for occasional discovery.
- **Low-risk**: no ToS-violating evasion, so no bans, no legal exposure, low maintenance.
- **Switchable**: `SEARCH_BACKEND` lets you choose SerpAPI, crawler, or both.

That is a crawler that is genuinely powerful — because it gets clean data from places that hand it over
willingly, instead of fighting systems designed to keep bots out.

---

*If/when these phases are implemented, update `PROJECT_GUIDE.md` (sections 5 and 15) and the README in
the same change.*
