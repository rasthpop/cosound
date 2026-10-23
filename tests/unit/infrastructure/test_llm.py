"""OpenRouterLLM against httpx.MockTransport. No test touches the network."""

from __future__ import annotations

import json
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
    assert payload["provider"] == {"require_parameters": True}
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
