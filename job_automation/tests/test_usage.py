from __future__ import annotations

from datetime import UTC, datetime

from usage import UsageTracker


class _Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def test_blocks_at_95_percent():
    tracker = UsageTracker(path=None, limits={"serpapi": 100}, block_ratio=0.95)
    # 95% of 100 -> threshold 95: allowed up to 95 recorded, then blocked.
    for _ in range(95):
        assert tracker.consume("serpapi") is True
    assert tracker.used("serpapi") == 95
    assert tracker.allow("serpapi") is False
    assert tracker.consume("serpapi") is False  # blocked, not recorded
    assert tracker.used("serpapi") == 95
    assert tracker.remaining("serpapi") == 5  # the 5-call safety buffer is never spent


def test_unlimited_provider_never_blocks():
    tracker = UsageTracker(path=None, limits={}, block_ratio=0.95)
    for _ in range(1000):
        assert tracker.consume("remoteok") is True
    assert tracker.used("remoteok") == 1000
    assert tracker.remaining("remoteok") is None
    assert tracker.allow("remoteok") is True


def test_monthly_rollover_resets_counts():
    clock = _Clock(datetime(2026, 6, 25, tzinfo=UTC))
    tracker = UsageTracker(path=None, limits={"brave": 2000}, clock=clock)
    tracker.record("brave", 50)
    assert tracker.used("brave") == 50

    clock.value = datetime(2026, 7, 1, tzinfo=UTC)  # new month
    assert tracker.used("brave") == 0
    assert tracker.month == "2026-07"


def test_persistence_round_trip(tmp_path):
    path = tmp_path / "usage.json"
    clock = _Clock(datetime(2026, 6, 25, tzinfo=UTC))
    first = UsageTracker(path=path, limits={"serpapi": 100}, clock=clock)
    first.record("serpapi", 7)
    first.save()

    second = UsageTracker(path=path, limits={"serpapi": 100}, clock=clock)
    assert second.used("serpapi") == 7


def test_persistence_ignores_other_month(tmp_path):
    path = tmp_path / "usage.json"
    june = _Clock(datetime(2026, 6, 25, tzinfo=UTC))
    UsageTracker(path=path, limits={}, clock=june).record("x", 5)
    UsageTracker(path=path, limits={}, clock=june).save()  # not dirty -> nothing; ensure file via explicit
    t = UsageTracker(path=path, limits={}, clock=june)
    t.record("x", 5)
    t.save()

    july = _Clock(datetime(2026, 7, 2, tzinfo=UTC))
    fresh = UsageTracker(path=path, limits={}, clock=july)
    assert fresh.used("x") == 0  # last month's file is not loaded into the new month


def test_report_rows_includes_limits_and_percent():
    tracker = UsageTracker(path=None, limits={"brave": 200})
    tracker.record("brave", 100)
    tracker.record("remoteok", 3)
    rows = {row["provider"]: row for row in tracker.report_rows()}
    assert rows["brave"]["percent"] == 50.0
    assert rows["brave"]["remaining"] == 100
    assert rows["remoteok"]["limit"] is None
