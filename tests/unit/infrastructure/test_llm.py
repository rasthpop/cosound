"""OpenRouterLLM against httpx.MockTransport. No test touches the network."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from music_discovery.infrastructure.llm import OpenRouterLLM, build_llm
from music_discovery.infrastructure.settings import Settings

KEY = "sk-or-test-secret"
JSON_MODEL = "vendor/json:free"
TOOL_MODEL = "vendor/tool:free"
PLAIN_MODEL = "vendor/plain:free"
CAPABILITIES = {
    JSON_MODEL: frozenset({"structured_outputs", "response_format", "tools", "tool_choice"}),
    TOOL_MODEL: frozenset({"tools", "tool_choice"}),
    PLAIN_MODEL: frozenset({"temperature"}),
}


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mood: str


Handler = Callable[[httpx.Request], httpx.Response]


def content(text: str, model: str) -> httpx.Response:
    return httpx.Response(200, json={"model": model, "choices": [{"message": {"content": text}}]})


def tool_call(arguments: str, model: str) -> httpx.Response:
    call = {"type": "function", "function": {"name": "Answer", "arguments": arguments}}
    message = {"content": None, "tool_calls": [call]}
    return httpx.Response(200, json={"model": model, "choices": [{"message": message}]})


class Recorder:
    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self.responses = responses
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def payload(self, i: int) -> dict[str, Any]:
        body: dict[str, Any] = json.loads(self.requests[i].content)
        return body


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def adapter(
    recorder: Recorder, models: list[str], clock: Clock | None = None, **kwargs: Any
) -> OpenRouterLLM:
    clock = clock or Clock()
    return OpenRouterLLM(
        api_key=SecretStr(KEY),
        models=models,
        capabilities=kwargs.pop("capabilities", CAPABILITIES),
        transport=httpx.MockTransport(recorder),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        **kwargs,
    )


def generate(llm: OpenRouterLLM, task: str = "query") -> Any:
    return llm.generate(task=task, system="system prompt", user="something chill", schema=Answer)


# --- output strategies ------------------------------------------------------------------


def test_json_schema_strategy() -> None:
    rec = Recorder([content('{"mood": "chill"}', JSON_MODEL)])
    result = generate(adapter(rec, [JSON_MODEL]))
    assert result.parsed == Answer(mood="chill")
    assert result.model_id == JSON_MODEL
    payload = rec.payload(0)
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["schema"] == Answer.model_json_schema()
    assert payload["provider"] == {"require_parameters": True, "data_collection": "deny"}
    assert payload["temperature"] == 0
    assert "tools" not in payload


def test_tool_call_strategy() -> None:
    rec = Recorder([tool_call('{"mood": "dark"}', TOOL_MODEL)])
    result = generate(adapter(rec, [TOOL_MODEL]))
    assert result.parsed == Answer(mood="dark")
    payload = rec.payload(0)
    assert payload["tools"][0]["function"]["parameters"] == Answer.model_json_schema()
    assert payload["tool_choice"]["function"]["name"] == "Answer"
    assert "response_format" not in payload


def test_prompt_only_strategy_extracts_first_json_object() -> None:
    rec = Recorder([content('Sure! ```json\n{"mood": "calm"}\n``` hope it helps', PLAIN_MODEL)])
    result = generate(adapter(rec, [PLAIN_MODEL]))
    assert result.parsed == Answer(mood="calm")
    payload = rec.payload(0)
    assert "response_format" not in payload
    assert "tools" not in payload
    assert "JSON schema" in payload["messages"][0]["content"]


def test_capabilities_are_read_from_the_models_endpoint() -> None:
    models = {"data": [{"id": TOOL_MODEL, "supported_parameters": ["tools", "tool_choice"]}]}
    rec = Recorder([httpx.Response(200, json=models), tool_call('{"mood": "dark"}', TOOL_MODEL)])
    result = generate(adapter(rec, [TOOL_MODEL], capabilities=None))
    assert result.parsed == Answer(mood="dark")
    assert rec.requests[0].url.path.endswith("/models")
    assert "tools" in rec.payload(1)


@pytest.mark.parametrize(
    "text", ['{"mood": ', '{"mood": "chill", "tempo": "fast"}', '{"mood": 3}', "no json"]
)
def test_invalid_output_is_an_error_result(text: str) -> None:
    rec = Recorder([content(text, JSON_MODEL)])
    result = generate(adapter(rec, [JSON_MODEL]))
    assert result.parsed is None
    assert result.error_code == "invalid_output"


# --- errors and fallback chain ----------------------------------------------------------


def test_rate_limit_respects_retry_after_then_retries() -> None:
    clock = Clock()
    rec = Recorder(
        [
            httpx.Response(429, headers={"Retry-After": "3"}),
            content('{"mood": "chill"}', JSON_MODEL),
        ]
    )
    result = generate(adapter(rec, [JSON_MODEL], clock))
    assert result.parsed == Answer(mood="chill")
    assert clock.slept == [3.0]


def test_rate_limit_exhausts_retries_then_next_model() -> None:
    clock = Clock()
    limited = [httpx.Response(429, headers={"Retry-After": "1"}) for _ in range(3)]
    rec = Recorder([*limited, tool_call('{"mood": "dark"}', TOOL_MODEL)])
    result = generate(adapter(rec, [JSON_MODEL, TOOL_MODEL], clock, max_retries=2))
    assert result.parsed == Answer(mood="dark")
    assert result.model_id == TOOL_MODEL
    assert [rec.payload(i)["model"] for i in range(4)] == [JSON_MODEL] * 3 + [TOOL_MODEL]
    assert rec.payload(0)["models"] == [JSON_MODEL, TOOL_MODEL]


def test_retry_after_is_capped() -> None:
    clock = Clock()
    rec = Recorder(
        [httpx.Response(429, headers={"Retry-After": "3600"}), content('{"mood": "x"}', JSON_MODEL)]
    )
    generate(adapter(rec, [JSON_MODEL], clock))
    assert clock.slept == [10.0]


def test_model_not_found_moves_to_next_model_without_retry() -> None:
    rec = Recorder(
        [
            httpx.Response(404, json={"error": {"message": "No endpoints found for model"}}),
            content('{"mood": "calm"}', PLAIN_MODEL),
        ]
    )
    result = generate(adapter(rec, [JSON_MODEL, PLAIN_MODEL]))
    assert result.parsed == Answer(mood="calm")
    assert result.model_id == PLAIN_MODEL
    assert len(rec.requests) == 2


def test_timeout_retries_then_reports() -> None:
    rec = Recorder([httpx.ReadTimeout("slow") for _ in range(3)])
    result = generate(adapter(rec, [JSON_MODEL], max_retries=2))
    assert result.error_code == "timeout"
    assert len(rec.requests) == 3


def test_quota_exhausted_stops_the_chain() -> None:
    rec = Recorder([httpx.Response(402, json={"error": {"message": "insufficient credits"}})])
    result = generate(adapter(rec, [JSON_MODEL, TOOL_MODEL]))
    assert result.error_code == "quota_exhausted"
    assert len(rec.requests) == 1


def test_upstream_error_with_http_200_is_unavailable() -> None:
    rec = Recorder([httpx.Response(200, json={"error": {"code": 502}}) for _ in range(3)])
    result = generate(adapter(rec, [JSON_MODEL], max_retries=2))
    assert result.error_code == "unavailable"


def test_per_task_model_goes_first() -> None:
    rec = Recorder([tool_call('{"mood": "dark"}', TOOL_MODEL)])
    llm = adapter(rec, [JSON_MODEL], task_models={"feedback": TOOL_MODEL})
    generate(llm, task="feedback")
    assert rec.payload(0)["model"] == TOOL_MODEL
    assert llm.chain("query") == [JSON_MODEL]


# --- circuit breaker --------------------------------------------------------------------


def test_circuit_breaker_opens_and_closes() -> None:
    clock = Clock()
    rec = Recorder([httpx.Response(503) for _ in range(3)])
    llm = adapter(
        rec, [JSON_MODEL], clock, max_retries=0, breaker_threshold=3, breaker_cooldown_s=60
    )
    assert [generate(llm).error_code for _ in range(3)] == ["unavailable"] * 3
    assert llm.status == "fallback"
    assert generate(llm).error_code == "circuit_open"
    assert len(rec.requests) == 3, "no request while open"

    clock.now += 61
    rec.responses.append(content('{"mood": "chill"}', JSON_MODEL))
    assert generate(llm).parsed == Answer(mood="chill")
    assert llm.status == "available"


def test_half_open_failure_reopens_immediately() -> None:
    clock = Clock()
    rec = Recorder([httpx.Response(503) for _ in range(4)])
    llm = adapter(
        rec, [JSON_MODEL], clock, max_retries=0, breaker_threshold=3, breaker_cooldown_s=60
    )
    for _ in range(3):
        generate(llm)
    clock.now += 61
    assert generate(llm).error_code == "unavailable"
    assert generate(llm).error_code == "circuit_open"


def test_invalid_output_does_not_trip_the_breaker() -> None:
    rec = Recorder([content("nope", JSON_MODEL) for _ in range(4)])
    llm = adapter(rec, [JSON_MODEL], breaker_threshold=3)
    assert [generate(llm).error_code for _ in range(4)] == ["invalid_output"] * 4
    assert llm.status == "available"


# --- cache, secrets, settings -----------------------------------------------------------


def test_cache_replays_without_a_request(tmp_path: Path) -> None:
    rec = Recorder([content('{"mood": "chill"}', JSON_MODEL)])
    llm = adapter(rec, [JSON_MODEL], cache_dir=tmp_path)
    first = generate(llm)
    second = generate(llm)
    assert first.parsed == second.parsed == Answer(mood="chill")
    assert second.model_id == JSON_MODEL
    assert len(rec.requests) == 1
    assert KEY not in "".join(p.read_text() for p in tmp_path.iterdir())


def test_key_is_sent_only_as_bearer_and_never_shown(caplog: pytest.LogCaptureFixture) -> None:
    rec = Recorder([httpx.Response(503) for _ in range(3)])
    llm = adapter(rec, [JSON_MODEL], app_title="SemanticMusicDiscovery")
    generate(llm)
    assert rec.requests[0].headers["Authorization"] == f"Bearer {KEY}"
    assert rec.requests[0].headers["X-Title"] == "SemanticMusicDiscovery"
    assert KEY not in repr(llm)
    assert KEY not in caplog.text
    assert KEY not in rec.requests[0].content.decode()


def test_build_llm_is_disabled_without_provider() -> None:
    assert build_llm(Settings(_env_file=None, llm_provider="")) is None  # type: ignore[call-arg]


def test_build_llm_needs_key_and_model() -> None:
    settings = Settings(_env_file=None, llm_provider="openrouter")  # type: ignore[call-arg]
    assert build_llm(settings) is None


def test_build_llm_uses_settings() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        llm_provider="openrouter",
        openrouter_api_key=KEY,
        llm_model=JSON_MODEL,
        llm_fallback_models=f"{TOOL_MODEL},{PLAIN_MODEL}",
        llm_model_query=PLAIN_MODEL,
    )
    llm = build_llm(settings)
    assert llm is not None
    assert llm.chain("query") == [PLAIN_MODEL, JSON_MODEL, TOOL_MODEL]
    assert llm.chain("feedback") == [JSON_MODEL, TOOL_MODEL, PLAIN_MODEL]


def test_build_llm_uses_the_search_budget_and_a_bounded_separate_cache(tmp_path: Path) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        llm_provider="openrouter",
        openrouter_api_key=KEY,
        llm_model=JSON_MODEL,
        llm_model_selection=TOOL_MODEL,
        llm_search_budget_s=7,
        llm_cache_max_entries=9,
        data_dir=tmp_path,
    )
    cached = build_llm(settings, cache=True)
    assert cached is not None
    assert cached.chain_budget_s == 7
    assert cached.cache_max_entries == 9
    assert cached.cache_dir == tmp_path / "llm_cache" / "api"
    assert cached.chain("selection") == [TOOL_MODEL, JSON_MODEL]
    plain = build_llm(settings)
    assert plain is not None
    assert plain.cache_dir is None


def test_model_statuses_flag_missing_paid_and_prompt_only_models() -> None:
    from music_discovery.infrastructure.llm import Strategy, model_statuses

    free = {"prompt": "0", "completion": "0"}
    catalog = [
        {"id": JSON_MODEL, "pricing": free, "supported_parameters": ["structured_outputs"]},
        {"id": TOOL_MODEL, "pricing": free, "supported_parameters": ["tools", "tool_choice"]},
        {"id": PLAIN_MODEL, "pricing": free, "supported_parameters": ["temperature"]},
        {"id": "vendor/paid", "pricing": {"prompt": "0.000001", "completion": "0"}},
    ]
    ids = [JSON_MODEL, TOOL_MODEL, PLAIN_MODEL, "vendor/paid", "vendor/gone:free", JSON_MODEL]
    statuses = {s.model_id: s for s in model_statuses(catalog, ids)}
    assert len(statuses) == 5
    assert statuses[JSON_MODEL].ok
    assert statuses[JSON_MODEL].strategy is Strategy.JSON_SCHEMA
    assert statuses[TOOL_MODEL].ok
    assert statuses[TOOL_MODEL].strategy is Strategy.TOOL
    assert (
        statuses[PLAIN_MODEL].problem == "no structured-output or tool support (prompt-only JSON)"
    )
    assert statuses["vendor/paid"].problem == "no longer free"
    assert statuses["vendor/gone:free"].problem == "not listed by OpenRouter (renamed or removed)"


@pytest.mark.parametrize("model", [JSON_MODEL, TOOL_MODEL, PLAIN_MODEL])
def test_every_strategy_denies_data_collection_by_default(model: str) -> None:
    answer = '{"mood": "x"}'
    response = tool_call(answer, model) if model == TOOL_MODEL else content(answer, model)
    rec = Recorder([response])
    generate(adapter(rec, [model]))
    assert rec.payload(0)["provider"]["data_collection"] == "deny"


def test_data_collection_follows_settings() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        llm_provider="openrouter",
        openrouter_api_key=KEY,
        llm_model=JSON_MODEL,
        llm_data_collection="allow",
    )
    llm = build_llm(settings)
    assert llm is not None
    assert llm.data_collection == "allow"
    assert Settings(_env_file=None).llm_data_collection == "deny"  # type: ignore[call-arg]


def test_model_refused_by_the_data_policy_falls_through() -> None:
    refused = httpx.Response(
        404, json={"error": {"message": "No endpoints found matching your data policy for model"}}
    )
    rec = Recorder([refused, content('{"mood": "calm"}', PLAIN_MODEL)])
    result = generate(adapter(rec, [JSON_MODEL, PLAIN_MODEL]))
    assert result.parsed == Answer(mood="calm")
    assert result.model_id == PLAIN_MODEL


def routing_404(step: str, message: str = "No endpoints found") -> httpx.Response:
    metadata = {"failed_routing_step": step}
    return httpx.Response(404, json={"error": {"message": message, "metadata": metadata}})


def test_response_format_alone_is_not_json_schema_support() -> None:
    from music_discovery.infrastructure.llm import Strategy, strategies_for

    gemma = frozenset({"response_format", "tools", "tool_choice", "reasoning"})
    assert strategies_for(gemma) == [Strategy.TOOL, Strategy.PROMPT]
    assert strategies_for(frozenset({"structured_outputs", "tools", "tool_choice"})) == [
        Strategy.JSON_SCHEMA,
        Strategy.TOOL,
        Strategy.PROMPT,
    ]
    assert strategies_for(frozenset({"response_format"})) == [Strategy.PROMPT]


def test_rejected_parameters_retry_the_same_model_with_the_next_strategy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rec = Recorder(
        [
            routing_404(
                "Filter by Parameters", "No endpoints found that can handle the parameters"
            ),
            tool_call('{"mood": "calm"}', JSON_MODEL),
        ]
    )
    result = generate(adapter(rec, [JSON_MODEL, TOOL_MODEL]))
    assert result.parsed == Answer(mood="calm")
    assert result.model_id == JSON_MODEL
    assert "response_format" in rec.payload(0)
    assert "tools" in rec.payload(1)
    assert "can handle the parameters" in caplog.text


def test_all_strategies_rejected_moves_to_the_next_model() -> None:
    rejected = [routing_404("Filter by Tool Compatibility") for _ in range(2)]
    rec = Recorder([*rejected, content('{"mood": "x"}', PLAIN_MODEL)])
    result = generate(adapter(rec, [TOOL_MODEL, PLAIN_MODEL]))
    assert result.model_id == PLAIN_MODEL
    assert [rec.payload(i)["model"] for i in range(3)] == [TOOL_MODEL, TOOL_MODEL, PLAIN_MODEL]
    assert "tools" in rec.payload(0)
    assert "tools" not in rec.payload(1), "second try is prompt-only JSON"


def test_data_policy_refusal_has_its_own_code() -> None:
    rec = Recorder([routing_404("Filter by Data Policy")])
    result = generate(adapter(rec, [JSON_MODEL]))
    assert result.error_code == "data_policy_refused"
    assert len(rec.requests) == 1


# --- search budget ----------------------------------------------------------------------


class SlowRecorder(Recorder):
    """Every request takes `seconds` of the fake clock."""

    def __init__(self, responses: list[httpx.Response | Exception], clock: Clock, seconds: float):
        super().__init__(responses)
        self.clock = clock
        self.seconds = seconds
        self.timeouts: list[float] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.clock.now += self.seconds
        self.timeouts.append(request.extensions["timeout"]["read"])
        return super().__call__(request)


def test_budget_stops_retries_and_the_rest_of_the_chain() -> None:
    clock = Clock()
    rec = SlowRecorder([httpx.ReadTimeout("slow") for _ in range(9)], clock, 6.0)
    llm = adapter(rec, [JSON_MODEL, TOOL_MODEL], clock, max_retries=2, chain_budget_s=10.0)
    result = generate(llm)
    assert result.error_code == "timeout"
    assert len(rec.requests) == 2, "the third attempt and the second model are over budget"
    assert rec.timeouts == [10.0, 4.0], "a request only gets what is left"


def test_callers_timeout_overrides_the_default_budget() -> None:
    clock = Clock()
    rec = SlowRecorder([httpx.ReadTimeout("slow") for _ in range(3)], clock, 2.0)
    llm = adapter(rec, [JSON_MODEL], clock, max_retries=2, chain_budget_s=100.0)
    result = llm.generate(task="query", system="s", user="u", schema=Answer, timeout_s=2.0)
    assert result.error_code == "timeout"
    assert len(rec.requests) == 1


def test_no_back_off_longer_than_the_budget() -> None:
    clock = Clock()
    rec = Recorder([httpx.Response(429, headers={"Retry-After": "8"})])
    llm = adapter(rec, [JSON_MODEL], clock, max_retries=2, chain_budget_s=5.0)
    assert generate(llm).error_code == "rate_limited"
    assert clock.slept == []


def test_failed_capability_fetch_is_not_remembered() -> None:
    models = {"data": [{"id": TOOL_MODEL, "supported_parameters": ["tools", "tool_choice"]}]}
    rec = Recorder(
        [
            httpx.ReadTimeout("slow"),
            content('{"mood": "calm"}', TOOL_MODEL),
            httpx.Response(200, json=models),
            tool_call('{"mood": "dark"}', TOOL_MODEL),
        ]
    )
    llm = adapter(rec, [TOOL_MODEL], capabilities=None)
    assert generate(llm).parsed == Answer(mood="calm")
    assert "tools" not in rec.payload(1)
    assert generate(llm).parsed == Answer(mood="dark")
    assert "tools" in rec.payload(3)


# --- daily quota ------------------------------------------------------------------------

NOW = 1_800_000_000.0


def limit_429(reset_in_s: float, *, remaining: str = "0", ms: bool = True) -> httpx.Response:
    reset = (NOW + reset_in_s) * (1000 if ms else 1)
    headers = {"X-RateLimit-Remaining": remaining, "X-RateLimit-Reset": str(int(reset))}
    return httpx.Response(429, headers=headers)


@pytest.mark.parametrize("ms", [True, False])
def test_used_up_daily_quota_makes_no_further_calls_until_reset(ms: bool) -> None:
    wall = {"now": NOW}
    rec = Recorder([limit_429(3600, ms=ms), content('{"mood": "chill"}', JSON_MODEL)])
    llm = adapter(rec, [JSON_MODEL, TOOL_MODEL], max_retries=2, wall_clock=lambda: wall["now"])
    assert generate(llm).error_code == "quota_exhausted"
    assert len(rec.requests) == 1, "no retry and no next model: the quota is per account"
    assert llm.status == "fallback"
    assert generate(llm).error_code == "quota_exhausted"
    assert len(rec.requests) == 1

    wall["now"] = NOW + 3601
    assert llm.status == "available"
    assert generate(llm).parsed == Answer(mood="chill")


@pytest.mark.parametrize(
    "response",
    [
        limit_429(30),
        limit_429(3600, remaining="4"),
        httpx.Response(429, headers={"X-RateLimit-Remaining": "0"}),
        httpx.Response(429, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "soon"}),
        httpx.Response(429),
    ],
    ids=["per-minute", "requests-left", "no-reset", "bad-reset", "no-headers"],
)
def test_other_rate_limits_are_retried_as_before(response: httpx.Response) -> None:
    rec = Recorder([response, content('{"mood": "chill"}', JSON_MODEL)])
    llm = adapter(rec, [JSON_MODEL], wall_clock=lambda: NOW)
    assert generate(llm).parsed == Answer(mood="chill")
    assert llm.status == "available"


def test_cached_answers_still_work_when_the_quota_is_used_up(tmp_path: Path) -> None:
    rec = Recorder([content('{"mood": "chill"}', JSON_MODEL), limit_429(3600)])
    llm = adapter(rec, [JSON_MODEL], cache_dir=tmp_path, wall_clock=lambda: NOW)
    assert generate(llm).parsed == Answer(mood="chill")
    other = llm.generate(task="query", system="s", user="other query", schema=Answer)
    assert other.error_code == "quota_exhausted"
    assert generate(llm).parsed == Answer(mood="chill")
    assert len(rec.requests) == 2


# --- bounded cache ----------------------------------------------------------------------


def test_cache_removes_the_oldest_entries_beyond_its_bound(tmp_path: Path) -> None:
    rec = Recorder([content('{"mood": "x"}', JSON_MODEL) for _ in range(4)])
    llm = adapter(rec, [JSON_MODEL], cache_dir=tmp_path, cache_max_entries=2)
    for i, user in enumerate(["a", "b", "c"]):
        llm.generate(task="query", system="s", user=user, schema=Answer)
        for path in tmp_path.iterdir():  # file times can tie on fast disks: order them explicitly
            if path.stat().st_mtime_ns > 1_000:
                os.utime(path, ns=(i, i))
    assert len(list(tmp_path.iterdir())) == 2
    llm.generate(task="query", system="s", user="c", schema=Answer)
    assert len(rec.requests) == 3, "the newest entry survives and replays"
    llm.generate(task="query", system="s", user="a", schema=Answer)
    assert len(rec.requests) == 4, "the oldest entry was removed"


def test_cache_entries_hold_no_identifiers(tmp_path: Path) -> None:
    rec = Recorder([content('{"mood": "chill"}', JSON_MODEL)])
    llm = adapter(rec, [JSON_MODEL], cache_dir=tmp_path)
    llm.generate(task="query", system="s", user="secret user text", schema=Answer)
    entry = json.loads(next(tmp_path.iterdir()).read_text())
    assert set(entry) == {"model_id", "raw_text", "created_at"}
    assert "secret user text" not in json.dumps(entry)
