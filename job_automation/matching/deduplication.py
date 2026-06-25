from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from database.models import Job


TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "ref", "source"}
COMPANY_SUFFIXES = (" gmbh", " ltd", " inc", " llc", " ag", " se")
# Gender/seniority/mode markers that should not make two postings look distinct.
GENDER_SENIORITY_NOISE = r"\b(junior|senior|lead|principal|staff|remote|hybrid|onsite|m f d|m w d|w m d|f m d|d f m|all genders|m w x|w m x)\b"


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for suffix in COMPANY_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    return normalized


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query) if key.lower() not in TRACKING_PARAMS])
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def prepare_deduplication(job: Job) -> Job:
    normalized_title = normalize_text(job.job_title)
    normalized_company = normalize_text(job.company_name)
    location = normalize_text(job.location)
    url = normalize_url(job.job_url)
    job.job_url = url
    job.normalized_title = normalized_title
    job.normalized_company = normalized_company
    job.deduplication_key = url or build_job_signature(normalized_title, normalized_company, location)
    return job


def title_core(normalized_title: str) -> str:
    """A title stripped of gender/seniority/mode markers, for near-duplicate matching."""
    title = re.sub(GENDER_SENIORITY_NOISE, " ", normalized_title)
    return re.sub(r"\s+", " ", title).strip()


def build_job_signature(normalized_title: str, normalized_company: str, location: str) -> str:
    title = title_core(normalized_title)
    location_key = "remote" if "remote" in location else location[:30]
    return "|".join(part for part in [title, normalized_company, location_key] if part)


def _token_set_ratio(left: str, right: str) -> float:
    """RapidFuzz-style token-set similarity using only the standard library.

    Sorting tokens makes word-order irrelevant ("ai automation specialist" ==
    "specialist automation ai") and comparing the shared-token set against each
    side absorbs extra trailing words (a subset still scores ~1.0). Good enough
    for the few-hundred-job batches here without adding a dependency.
    """
    left_tokens, right_tokens = set(left.split()), set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = " ".join(sorted(left_tokens & right_tokens))
    sorted_left = " ".join(sorted(left_tokens))
    sorted_right = " ".join(sorted(right_tokens))
    return max(
        SequenceMatcher(None, intersection, sorted_left).ratio(),
        SequenceMatcher(None, intersection, sorted_right).ratio(),
        SequenceMatcher(None, sorted_left, sorted_right).ratio(),
    )


def _is_richer(candidate: Job, current: Job) -> bool:
    """Whether ``candidate`` is the better record to keep when collapsing a pair."""
    cand_known = bool(candidate.company_name) and candidate.company_name != "Unknown"
    curr_known = bool(current.company_name) and current.company_name != "Unknown"
    if cand_known != curr_known:
        return cand_known
    return len(candidate.job_description or "") > len(current.job_description or "")


def _merge_into(keep: Job, drop: Job) -> None:
    """Backfill empty fields on the kept posting from the dropped near-duplicate."""
    if keep.company_name in ("", "Unknown") and drop.company_name not in ("", "Unknown"):
        keep.company_name = drop.company_name
    for field in ("location", "salary", "date_posted", "job_description", "required_skills"):
        if not getattr(keep, field, "") and getattr(drop, field, ""):
            setattr(keep, field, getattr(drop, field))


def _is_known_company(job: Job) -> bool:
    return bool(job.company_name) and job.company_name != "Unknown"


def _company_similarity(left: Job, right: Job) -> float:
    # An Unknown/empty company is a wildcard: it attaches to a known company with
    # the same title rather than blocking the merge.
    if not _is_known_company(left) or not _is_known_company(right):
        return 1.0
    return _token_set_ratio(left.normalized_company, right.normalized_company)


def collapse_near_duplicates(jobs: list[Job], title_threshold: float = 0.86, company_threshold: float = 0.84) -> list[Job]:
    """Second-pass collapse of postings that exact-key dedup misses.

    Two postings are the same job when their marker-stripped titles are highly
    similar AND their companies match -- e.g. a role posted as "(m/f/d)" and
    "(m/w/d)", the same opening with slightly different company strings
    ("Vetaion GmbH" vs "Vetaion GmbH in"), or a known company attached to an
    Unknown-company copy from another source. Blocking on the first characters of
    the marker-stripped title keeps this near-linear.
    """
    kept: list[Job] = []
    buckets: dict[str, list[int]] = {}
    for job in jobs:
        core = title_core(job.normalized_title)
        title_key = re.sub(r"[^a-z0-9]", "", core)[:6]
        block = buckets.setdefault(title_key, [])
        match_index = None
        for index in block:
            other = kept[index]
            if _token_set_ratio(core, title_core(other.normalized_title)) < title_threshold:
                continue
            if _company_similarity(job, other) >= company_threshold:
                match_index = index
                break
        if match_index is None:
            block.append(len(kept))
            kept.append(job)
        elif _is_richer(job, kept[match_index]):
            _merge_into(job, kept[match_index])
            kept[match_index] = job
        else:
            _merge_into(kept[match_index], job)
    return kept


def deduplicate_jobs(jobs: list[Job]) -> list[Job]:
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()
    seen_signatures: set[str] = set()
    unique_jobs: list[Job] = []
    for job in jobs:
        prepared = prepare_deduplication(job)
        signature = build_job_signature(prepared.normalized_title, prepared.normalized_company, normalize_text(prepared.location))
        if prepared.job_url and prepared.job_url in seen_urls:
            continue
        if prepared.deduplication_key in seen_keys:
            continue
        if signature in seen_signatures:
            continue
        if prepared.job_url:
            seen_urls.add(prepared.job_url)
        seen_keys.add(prepared.deduplication_key)
        seen_signatures.add(signature)
        unique_jobs.append(prepared)
    return collapse_near_duplicates(unique_jobs)
