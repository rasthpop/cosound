"""DiscogsClient against httpx.MockTransport. No test touches the network."""

from __future__ import annotations

import json
import random
import socket
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from music_discovery.domain.errors import (
    DiscogsAuthError,
    DiscogsNotFound,
    DiscogsRateLimited,
    DiscogsResponseInvalid,
    DiscogsUnavailable,
)
from music_discovery.ingestion.discogs_client import DiscogsClient
from music_discovery.ingestion.rate_limit import RateLimiter, RetryPolicy
from tests.fakes import FrozenClock

Handler = Callable[[httpx.Request], httpx.Response]
RELEASE = {"id": 1, "title": "Album", "year": 1999, "uri": "https://www.discogs.com/release/1"}


def make_client(
    handler: Handler,
    clock: FrozenClock,
    *,
    token: str | None = "secret-token",
    retry: RetryPolicy | None = None,
    limiter: RateLimiter | None = None,
) -> DiscogsClient:
    return DiscogsClient(
        httpx.Client(transport=httpx.MockTransport(handler)),
        user_agent="SemanticMusicDiscovery/test",
        token=token,
        clock=clock,
        retry=retry or RetryPolicy(max_attempts=3, base_delay_s=1.0, jitter=0.0),
        limiter=limiter,
        rng=random.Random(0),
    )


def respond(
    status: int = 200, body: Any = RELEASE, headers: dict[str, str] | None = None
) -> httpx.Response:
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return httpx.Response(status, content=content, headers=headers or {})


class Recorder:
    """Replays responses in order and records the requests it saw."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_success_sends_identity_and_auth_headers(clock: FrozenClock) -> None:
    rec = Recorder(respond())
    release = make_client(rec, clock).get_release(1)
    assert release.title == "Album"
    request = rec.requests[0]
    assert request.url.path == "/releases/1"
    assert request.headers["User-Agent"] == "SemanticMusicDiscovery/test"
    assert request.headers["Authorization"] == "Discogs token=secret-token"


def test_no_token_sends_no_auth_header(clock: FrozenClock) -> None:
    rec = Recorder(respond())
    make_client(rec, clock, token=None).get_release(1)
    assert "Authorization" not in rec.requests[0].headers


def test_empty_user_agent_rejected(clock: FrozenClock) -> None:
    with pytest.raises(ValueError, match="User-Agent"):
        DiscogsClient(httpx.Client(), user_agent=" ", token=None, clock=clock)


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (404, DiscogsNotFound),
        (401, DiscogsAuthError),
        (403, DiscogsAuthError),
        (400, DiscogsResponseInvalid),
    ],
)
def test_client_errors_are_classified_without_retry(
    clock: FrozenClock, status: int, error: type[Exception]
) -> None:
    rec = Recorder(respond(status, {"message": "nope"}))
    with pytest.raises(error):
        make_client(rec, clock).get_release(1)
    assert len(rec.requests) == 1


def test_429_with_retry_after_waits_that_long(clock: FrozenClock) -> None:
    rec = Recorder(respond(429, {}, {"Retry-After": "7"}), respond())
    start = clock.now()
    assert make_client(rec, clock).get_release(1).id == 1
    assert (clock.now() - start).total_seconds() >= 7


def test_429_without_retry_after_backs_off_then_gives_up(clock: FrozenClock) -> None:
    rec = Recorder(respond(429, {}), respond(429, {}), respond(429, {}))
    start = clock.now()
    with pytest.raises(DiscogsRateLimited) as info:
        make_client(rec, clock).get_release(1)
    assert info.value.retry_after_s is None
    assert len(rec.requests) == 3
    assert (clock.now() - start).total_seconds() >= 1 + 2  # exponential backoff, no jitter


def test_5xx_then_success(clock: FrozenClock) -> None:
    rec = Recorder(respond(502, {}), respond(503, {}), respond())
    assert make_client(rec, clock).get_release(1).id == 1
    assert len(rec.requests) == 3


def test_timeout_and_connection_errors_retry_then_raise(clock: FrozenClock) -> None:
    rec = Recorder(
        httpx.ReadTimeout("slow"), httpx.ConnectError("down"), httpx.ConnectError("down")
    )
    with pytest.raises(DiscogsUnavailable):
        make_client(rec, clock).get_release(1)
    assert len(rec.requests) == 3


def test_malformed_json_is_invalid_and_not_retried(clock: FrozenClock) -> None:
    rec = Recorder(respond(200, b"{not json"))
    with pytest.raises(DiscogsResponseInvalid):
        make_client(rec, clock).get_release(1)
    assert len(rec.requests) == 1


def test_wrong_shape_is_invalid(clock: FrozenClock) -> None:
    rec = Recorder(respond(200, {"id": "not-a-number"}))
    with pytest.raises(DiscogsResponseInvalid):
        make_client(rec, clock).get_release(1)


def page(n: int, pages: int, ids: list[int]) -> httpx.Response:
    return respond(
        body={
            "pagination": {"page": n, "pages": pages, "per_page": len(ids) or 1, "items": 99},
            "releases": [{"id": i, "title": f"R{i}", "type": "release"} for i in ids],
        }
    )


def test_pagination_stops_at_max_items(clock: FrozenClock) -> None:
    rec = Recorder(page(1, 5, [1, 2, 3]), page(2, 5, [4, 5, 6]))
    items = list(make_client(rec, clock).iter_artist_releases(9, max_items=5))
    assert [i.id for i in items] == [1, 2, 3, 4, 5]
    assert len(rec.requests) == 2
    assert rec.requests[0].url.params["per_page"] == "5"
    assert rec.requests[1].url.params["page"] == "2"


def test_pagination_stops_at_last_page(clock: FrozenClock) -> None:
    rec = Recorder(page(1, 2, [1, 2]), page(2, 2, [3]))
    items = list(make_client(rec, clock).iter_label_releases(4, max_items=100))
    assert [i.id for i in items] == [1, 2, 3]
    assert rec.requests[0].url.path == "/labels/4/releases"
    assert rec.requests[0].url.params["per_page"] == "100"


def test_zero_max_items_makes_no_request(clock: FrozenClock) -> None:
    rec = Recorder()
    assert list(make_client(rec, clock).iter_artist_releases(1, max_items=0)) == []
    assert rec.requests == []


def test_search_requires_token(clock: FrozenClock) -> None:
    with pytest.raises(DiscogsAuthError):
        make_client(Recorder(), clock, token=None).search(max_items=5, style="Ambient")


def test_search_sends_filters(clock: FrozenClock) -> None:
    rec = Recorder(
        respond(
            body={
                "pagination": {"page": 1, "pages": 1, "per_page": 2, "items": 1},
                "results": [{"id": 7, "type": "release", "title": "X", "master_id": 0}],
            }
        )
    )
    hits = list(make_client(rec, clock).search(max_items=2, genre="Jazz", style="Cool Jazz"))
    assert hits[0].master_id is None
    params = rec.requests[0].url.params
    assert (params["genre"], params["style"], params["type"]) == ("Jazz", "Cool Jazz", "release")


def test_header_driven_slowdown(clock: FrozenClock) -> None:
    exhausted = {"X-Discogs-Ratelimit": "60", "X-Discogs-Ratelimit-Remaining": "0"}
    rec = Recorder(respond(headers=exhausted), respond())
    client = make_client(rec, clock, limiter=RateLimiter(clock, 60))
    start = clock.now()
    client.get_release(1)
    client.get_release(1)
    # with zero tokens left, the second request waits for one token at 1 req/s
    assert (clock.now() - start).total_seconds() == pytest.approx(1.0, abs=0.01)


def test_rate_limiter_spaces_requests_after_burst(clock: FrozenClock) -> None:
    limiter = RateLimiter(clock, 25)
    waits = [limiter.acquire() for _ in range(26)]
    assert waits[:25] == [0.0] * 25
    assert waits[25] == pytest.approx(60 / 25)


def test_token_never_logged(clock: FrozenClock, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")
    make_client(Recorder(respond()), clock).get_release(1)
    assert "secret-token" not in caplog.text
    assert any(r.message == "discogs request" for r in caplog.records)


def test_real_sockets_are_blocked() -> None:
    with pytest.raises(RuntimeError, match="network access is blocked"):
        socket.create_connection(("api.discogs.com", 443))
