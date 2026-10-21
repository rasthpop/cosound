"""Discogs API client: the only module that talks HTTP to Discogs.

Responsibilities (base.md §10.1): authentication, request construction, response validation,
pagination, retry with backoff, rate limiting, request logging, and error classification.
It never parallelizes requests and every iterator is bounded by `max_items`.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Iterator, Mapping
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from music_discovery.domain.errors import (
    DiscogsAuthError,
    DiscogsNotFound,
    DiscogsRateLimited,
    DiscogsResponseInvalid,
    DiscogsUnavailable,
)
from music_discovery.domain.protocols import Clock
from music_discovery.ingestion.discogs_models import (
    DiscogsArtist,
    DiscogsMaster,
    DiscogsPagination,
    DiscogsRelease,
    DiscogsReleaseSummary,
    DiscogsSearchHit,
)
from music_discovery.ingestion.rate_limit import RateLimiter, RetryPolicy

DEFAULT_BASE_URL = "https://api.discogs.com"
MAX_PER_PAGE = 100
AUTHENTICATED_RPM = 60
UNAUTHENTICATED_RPM = 25

M = TypeVar("M", bound=BaseModel)


def _int_header(headers: httpx.Headers, name: str) -> int | None:
    value = headers.get(name)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _retry_after(headers: httpx.Headers) -> float | None:
    value = headers.get("Retry-After")
    try:
        return max(0.0, float(value)) if value is not None else None
    except ValueError:
        return None


class _RetryableError(Exception):
    def __init__(self, error: Exception, wait_s: float | None = None) -> None:
        super().__init__(str(error))
        self.error = error
        self.wait_s = wait_s


class DiscogsClient:
    def __init__(
        self,
        http: httpx.Client,
        *,
        user_agent: str,
        token: str | None,
        clock: Clock,
        limiter: RateLimiter | None = None,
        retry: RetryPolicy | None = None,
        logger: logging.Logger | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 20.0,
        rng: random.Random | None = None,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("Discogs requires a User-Agent that identifies the application")
        self._http = http
        self._user_agent = user_agent
        self._token = token
        self._clock = clock
        rpm = AUTHENTICATED_RPM if token else UNAUTHENTICATED_RPM
        self._limiter = limiter or RateLimiter(clock, rpm)
        self._retry = retry or RetryPolicy()
        self._log = logger or logging.getLogger(__name__)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s
        self._rng = rng or random.Random()

    # --- Public endpoints ---------------------------------------------------------

    def get_release(self, release_id: int) -> DiscogsRelease:
        return self._get_model(f"/releases/{release_id}", DiscogsRelease)

    def get_release_raw(self, release_id: int) -> dict[str, Any]:
        """Unparsed payload, for the importer's raw cache. Still validated before returning."""
        payload = self._request(f"/releases/{release_id}")
        self._validate(DiscogsRelease, payload, f"/releases/{release_id}")
        return payload

    def get_master(self, master_id: int) -> DiscogsMaster:
        return self._get_model(f"/masters/{master_id}", DiscogsMaster)

    def get_artist(self, artist_id: int) -> DiscogsArtist:
        return self._get_model(f"/artists/{artist_id}", DiscogsArtist)

    def iter_artist_releases(
        self, artist_id: int, *, max_items: int
    ) -> Iterator[DiscogsReleaseSummary]:
        return self._paginate(
            f"/artists/{artist_id}/releases", "releases", DiscogsReleaseSummary, max_items
        )

    def iter_label_releases(
        self, label_id: int, *, max_items: int
    ) -> Iterator[DiscogsReleaseSummary]:
        return self._paginate(
            f"/labels/{label_id}/releases", "releases", DiscogsReleaseSummary, max_items
        )

    def search(
        self,
        *,
        max_items: int,
        genre: str | None = None,
        style: str | None = None,
        type: str = "release",
    ) -> Iterator[DiscogsSearchHit]:
        if not self._token:
            raise DiscogsAuthError("Discogs database search requires DISCOGS_TOKEN")
        params: dict[str, str] = {"type": type}
        if genre:
            params["genre"] = genre
        if style:
            params["style"] = style
        return self._paginate("/database/search", "results", DiscogsSearchHit, max_items, params)

    # --- Internals --------------------------------------------------------------------

    def _get_model(self, path: str, model: type[M]) -> M:
        return self._validate(model, self._request(path), path)

    @staticmethod
    def _validate(model: type[M], payload: Mapping[str, Any], path: str) -> M:
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            raise DiscogsResponseInvalid(
                f"unexpected response shape from {path}",
                details={"path": path, "errors": exc.errors(include_url=False)[:5]},
            ) from exc

    def _paginate(
        self,
        path: str,
        key: str,
        model: type[M],
        max_items: int,
        params: Mapping[str, str] | None = None,
    ) -> Iterator[M]:
        if max_items <= 0:
            return
        per_page = min(MAX_PER_PAGE, max_items)
        page = 1
        yielded = 0
        while True:
            query = {**(params or {}), "page": str(page), "per_page": str(per_page)}
            payload = self._request(path, query)
            items = payload.get(key)
            if not isinstance(items, list):
                raise DiscogsResponseInvalid(
                    f"missing '{key}' list in {path}", details={"path": path}
                )
            pagination = self._validate(DiscogsPagination, payload.get("pagination", {}), path)
            for item in items:
                yield self._validate(model, item, path)
                yielded += 1
                if yielded >= max_items:
                    return
            if page >= pagination.pages or not items:
                return
            page += 1

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Discogs token={self._token}"
        return headers

    def _request(self, path: str, params: Mapping[str, str] | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                return self._attempt(path, params)
            except _RetryableError as retryable:
                last_error = retryable.error
                if attempt == self._retry.max_attempts:
                    break
                wait = retryable.wait_s
                if wait is None:
                    wait = self._retry.delay(attempt, self._rng)
                self._log.warning(
                    "discogs retry",
                    extra={
                        "path": path,
                        "attempt": attempt,
                        "wait_s": round(wait, 2),
                        "error": type(retryable.error).__name__,
                    },
                )
                self._clock.sleep(wait)
        assert last_error is not None
        raise last_error

    def _attempt(self, path: str, params: Mapping[str, str] | None) -> dict[str, Any]:
        self._limiter.acquire()
        started = time.perf_counter()
        try:
            response = self._http.get(
                f"{self._base_url}{path}",
                params=params,
                headers=self._headers(),
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise _RetryableError(
                DiscogsUnavailable(f"timeout calling {path}", details={"path": path})
            ) from exc
        except httpx.TransportError as exc:
            raise _RetryableError(
                DiscogsUnavailable(f"connection error calling {path}", details={"path": path})
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        remaining = _int_header(response.headers, "X-Discogs-Ratelimit-Remaining")
        self._limiter.observe(_int_header(response.headers, "X-Discogs-Ratelimit"), remaining)
        self._log.info(
            "discogs request",
            extra={
                "method": "GET",
                "path": path,
                "status": response.status_code,
                "latency_ms": round(latency_ms, 1),
                "ratelimit_remaining": remaining,
            },
        )
        return self._classify(response, path)

    @staticmethod
    def _classify(response: httpx.Response, path: str) -> dict[str, Any]:
        status = response.status_code
        details: dict[str, Any] = {"path": path, "status": status}
        if status == 200:
            try:
                payload = response.json()
            except ValueError as exc:
                raise DiscogsResponseInvalid(f"invalid JSON from {path}", details=details) from exc
            if not isinstance(payload, dict):
                raise DiscogsResponseInvalid(f"expected a JSON object from {path}", details=details)
            return payload
        if status == 429:
            wait = _retry_after(response.headers)
            raise _RetryableError(
                DiscogsRateLimited(f"rate limited on {path}", retry_after_s=wait, details=details),
                wait_s=wait,
            )
        if status >= 500:
            raise _RetryableError(
                DiscogsUnavailable(f"Discogs returned {status} for {path}", details=details)
            )
        if status == 404:
            raise DiscogsNotFound(f"{path} not found", details=details)
        if status in (401, 403):
            raise DiscogsAuthError(f"Discogs refused {path} ({status})", details=details)
        raise DiscogsResponseInvalid(f"unexpected status {status} for {path}", details=details)
