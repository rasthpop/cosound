"""Client-side rate limiting and retry policy for external APIs."""

from __future__ import annotations

import random
from dataclasses import dataclass

from music_discovery.domain.protocols import Clock


class RateLimiter:
    """Token bucket refilled continuously; shrinks to the server's reported remaining budget.

    `requests_per_minute` should match the documented limit (Discogs: 60 with a token,
    25 without). Waiting goes through the injected clock, so tests run instantly.
    """

    def __init__(self, clock: Clock, requests_per_minute: int) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        self._clock = clock
        self._capacity = float(requests_per_minute)
        self._rate = requests_per_minute / 60.0
        self._tokens = self._capacity
        self._updated = clock.now().timestamp()

    def acquire(self) -> float:
        """Take one token, sleeping until one is available. Returns the seconds waited."""
        self._refill()
        waited = 0.0
        if self._tokens < 1.0:
            waited = (1.0 - self._tokens) / self._rate
            self._clock.sleep(waited)
            self._refill()
        self._tokens -= 1.0
        return waited

    def observe(self, limit: int | None, remaining: int | None) -> None:
        """Trust the server: never hold more tokens than it says remain in its window."""
        if limit is not None and limit > 0 and limit != self._capacity:
            self._capacity = float(limit)
            self._rate = limit / 60.0
        if remaining is not None:
            self._tokens = min(self._tokens, float(max(remaining, 0)))

    def _refill(self) -> None:
        now = self._clock.now().timestamp()
        elapsed = max(0.0, now - self._updated)
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._updated = now


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff with jitter for transient failures."""

    max_attempts: int = 4
    base_delay_s: float = 1.0
    max_delay_s: float = 30.0
    jitter: float = 0.25

    def delay(self, attempt: int, rng: random.Random) -> float:
        """Delay before retry number `attempt` (1-based)."""
        base = min(self.max_delay_s, self.base_delay_s * 2.0 ** (attempt - 1))
        return float(base * (1.0 + rng.uniform(-self.jitter, self.jitter)))
