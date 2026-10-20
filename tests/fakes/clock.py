from datetime import UTC, datetime, timedelta


class FrozenClock:
    """Clock that only moves when a test advances it."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)

    def sleep(self, seconds: float) -> None:
        """Stand-in for `time.sleep` in code under test (rate limiting, backoff)."""
        self.advance(seconds)
