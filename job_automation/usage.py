"""Monthly usage counter + quota guard for every API / scraper.

Why: some search providers cost money (SerpAPI) or have a free-tier monthly
allowance (Brave ~2000/month, DuckDuckGo gets rate-limited if hammered). This
tracker persists a per-provider count for the current calendar month and refuses
further calls once a provider reaches ``block_ratio`` (95%) of its limit, so a run
can never blow a budget or trigger a charge. Free/unlimited sources are still
counted (limit ``None``) for visibility, just never blocked.

A single module-level ``tracker`` is shared by every scraper; it is saved to
``USAGE_FILE`` at process exit (and explicitly by ``main`` at end of run).
"""
from __future__ import annotations

import atexit
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from config import USAGE_BLOCK_RATIO, USAGE_FILE, USAGE_LIMITS


class UsageTracker:
    def __init__(
        self,
        path: Path | str | None,
        limits: dict[str, int] | None = None,
        block_ratio: float = 0.95,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path) if path else None
        self.limits = dict(limits or {})
        self.block_ratio = block_ratio
        self._now = clock or (lambda: datetime.now(UTC))
        self.month = self._current_month()
        self.counts: dict[str, int] = {}
        self._dirty = False
        self._load()

    # -- month handling ------------------------------------------------------

    def _current_month(self) -> str:
        return self._now().strftime("%Y-%m")

    def _roll_month_if_needed(self) -> None:
        current = self._current_month()
        if current != self.month:  # new calendar month -> counters reset
            self.month = current
            self.counts = {}
            self._dirty = True

    # -- queries -------------------------------------------------------------

    def limit(self, provider: str) -> int | None:
        return self.limits.get(provider)

    def used(self, provider: str) -> int:
        self._roll_month_if_needed()
        return self.counts.get(provider, 0)

    def remaining(self, provider: str) -> int | None:
        limit = self.limit(provider)
        return None if limit is None else max(0, limit - self.used(provider))

    def block_threshold(self, provider: str) -> int | None:
        """The count at which the provider is considered "at 95%" and blocked."""
        limit = self.limit(provider)
        return None if limit is None else int(limit * self.block_ratio)

    def allow(self, provider: str, n: int = 1) -> bool:
        """Whether ``n`` more calls are allowed without crossing the 95% line."""
        threshold = self.block_threshold(provider)
        if threshold is None:  # unlimited / unmetered source
            return True
        return self.used(provider) + n <= threshold

    def percent(self, provider: str) -> float | None:
        limit = self.limit(provider)
        if not limit:
            return None
        return round(100.0 * self.used(provider) / limit, 1)

    # -- mutations -----------------------------------------------------------

    def record(self, provider: str, n: int = 1) -> None:
        self._roll_month_if_needed()
        self.counts[provider] = self.counts.get(provider, 0) + n
        self._dirty = True

    def consume(self, provider: str, n: int = 1) -> bool:
        """Record ``n`` calls only if allowed; return False when blocked."""
        if not self.allow(provider, n):
            return False
        self.record(provider, n)
        return True

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        if not self.path:
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        if isinstance(data, dict) and data.get("month") == self.month:
            counts = data.get("counts", {})
            if isinstance(counts, dict):
                self.counts = {str(key): int(value) for key, value in counts.items()}

    def save(self) -> None:
        if not self.path or not self._dirty:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"month": self.month, "counts": self.counts}), encoding="utf-8")
            tmp.replace(self.path)
            self._dirty = False
        except OSError:
            pass

    # -- reporting -----------------------------------------------------------

    def report_rows(self) -> list[dict]:
        self._roll_month_if_needed()
        providers = sorted(set(self.counts) | set(self.limits))
        rows = []
        for provider in providers:
            limit = self.limit(provider)
            rows.append(
                {
                    "provider": provider,
                    "used": self.used(provider),
                    "limit": limit,
                    "remaining": self.remaining(provider),
                    "percent": self.percent(provider),
                    "blocked": not self.allow(provider),
                }
            )
        return rows


# Shared singleton used across the project.
tracker = UsageTracker(USAGE_FILE or None, USAGE_LIMITS, USAGE_BLOCK_RATIO)
atexit.register(tracker.save)
