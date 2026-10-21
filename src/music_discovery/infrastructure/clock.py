"""Real clock for composition roots. Tests use `tests.fakes.FrozenClock`."""

from __future__ import annotations

import time
from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)
