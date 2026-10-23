"""OpenRouter adapter for `domain.protocols.StructuredLLM` (free models, OpenAI-compatible API).

One call walks the model chain (the task's model or `LLM_MODEL`, then `LLM_FALLBACK_MODELS`):

- the structured-output strategy is chosen per model from `supported_parameters` in
  `GET /models`: `json_schema` response format (needs `structured_outputs`; `response_format`
  alone may mean JSON mode only) -> a forced tool call -> JSON-only prompt. If OpenRouter's
  routing rejects the parameters (404 at a "Filter by ..." step), the same model is retried
  with the next strategy. Every answer is validated with Pydantic; content is never repaired
  beyond code fences;
- 429 waits `Retry-After` (capped) and retries, then moves on; 5xx and timeouts retry, then
  move on; a model that is gone moves on at once; 402 (quota) stops the chain;
- after `breaker_threshold` failed calls in a row the circuit opens for `breaker_cooldown_s`
  and calls return `circuit_open` immediately, so searches do not wait on a dead provider;
- an optional response cache (evaluation runs) keys on model chain, task, schema and a hash
  of the prompts, so reruns are reproducible and stay inside free-tier limits;
- every request carries `provider.data_collection` ("deny" by default): OpenRouter then routes
  only to providers that do not store or train on inputs, whatever the account setting says.
  A model with no such provider is refused and the chain moves on (deterministic fallback last).

The API key is only ever placed in the Authorization header; it is never logged or cached.
Failures are returned as `LLMResult(error_code=...)`, never raised, so agents can fall back.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, TypeVar

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from music_discovery.domain.schemas import LLMResult
from music_discovery.infrastructure.settings import Settings

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger(__name__)

PROVIDER = "openrouter"
MAX_RETRY_AFTER_S = 10.0
DEFAULT_MAX_TOKENS: Mapping[str, int] = {"query": 800, "feedback": 400, "descriptions": 600}
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")
JSON_ONLY_INSTRUCTION = (
    "Answer with one JSON object only, no prose and no code fences, matching this JSON schema:"
)


class Strategy(StrEnum):
    JSON_SCHEMA = "json_schema"
    TOOL = "tool"
    PROMPT = "prompt"


class _CallError(Exception):
    def __init__(
        self, code: str, *, retryable: bool = False, wait_s: float = 0.0, detail: str = ""
    ) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.wait_s = wait_s
        self.detail = detail


@dataclass
class _Breaker:
    threshold: int
    cooldown_s: float
    failures: int = 0
    opened_at: float | None = None

    def is_open(self, now: float) -> bool:
        if self.opened_at is None:
            return False
        if now - self.opened_at >= self.cooldown_s:
            self.opened_at = None  # half-open: let one call through
            self.failures = self.threshold - 1
            return False
        return True

    def record(self, ok: bool, now: float) -> None:
        if ok:
            self.failures, self.opened_at = 0, None
            return
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = now


@dataclass
class OpenRouterLLM:
    api_key: SecretStr = field(repr=False)
    models: Sequence[str]
    """Primary first, then fallbacks; every id should be a `:free` variant."""
    base_url: str = "https://openrouter.ai/api/v1"
    task_models: Mapping[str, str] = field(default_factory=dict)
    """Per-task primary overrides ("query", "feedback", "descriptions")."""
    timeout_s: float = 20.0
    max_retries: int = 2
    app_title: str | None = None
    http_referer: str | None = None
    breaker_threshold: int = 3
    breaker_cooldown_s: float = 60.0
    cache_dir: Path | None = None
    data_collection: Literal["allow", "deny"] = "deny"
    """OpenRouter provider filter; "deny" = only providers that do not collect user data."""
    capabilities: Mapping[str, frozenset[str]] | None = None
    """`supported_parameters` per model; fetched from `GET /models` on first use when None."""
    transport: httpx.BaseTransport | None = field(default=None, repr=False)
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False)
    monotonic: Callable[[], float] = field(default=time.monotonic, repr=False)

    def __post_init__(self) -> None:
        if not self.models:
            raise ValueError("at least one model id is required")
        headers = {"Authorization": f"Bearer {self.api_key.get_secret_value()}"}
        if self.app_title:
            headers["X-Title"] = self.app_title
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout_s,
            transport=self.transport,
        )
        self._breaker = _Breaker(self.breaker_threshold, self.breaker_cooldown_s)

    # --- public -----------------------------------------------------------------------

    @property
    def status(self) -> str:
        """ "available", or "fallback" while the circuit is open (for /api/health)."""
        return "fallback" if self._breaker.is_open(self.monotonic()) else "available"

    def chain(self, task: str) -> list[str]:
        primary = self.task_models.get(task)
        ordered = [primary, *self.models] if primary else list(self.models)
        return list(dict.fromkeys(ordered))

    def generate(
        self,
        *,
        task: str,
        system: str,
        user: str,
        schema: type[T],
        timeout_s: float | None = None,
    ) -> LLMResult[T]:
        chain = self.chain(task)
        cache_key = self._cache_key(chain, task, system, user, schema)
        cached = self._cache_read(cache_key, schema)
        if cached is not None:
            return cached
        if self._breaker.is_open(self.monotonic()):
            return LLMResult[T](error_code="circuit_open")

        started = self.monotonic()
        result: LLMResult[T] = LLMResult[T](error_code="unavailable")
        for index, model in enumerate(chain):
            result = self._try_model(model, chain[index:], task, system, user, schema, timeout_s)
            if result.parsed is not None or result.error_code not in _NEXT_MODEL_CODES:
                break
        latency = (self.monotonic() - started) * 1000.0
        result = result.model_copy(update={"latency_ms": max(latency, 0.0)})
        # invalid output is the model's answer, not an outage: it does not trip the breaker
        self._breaker.record(result.error_code in (None, "invalid_output"), self.monotonic())
        if result.parsed is not None:
            self._cache_write(cache_key, result)
        else:
            log.warning("llm %s failed: %s (model=%s)", task, result.error_code, result.model_id)
        return result

    def close(self) -> None:
        self._client.close()

    # --- one model --------------------------------------------------------------------

    def _try_model(
        self,
        model: str,
        routing: Sequence[str],
        task: str,
        system: str,
        user: str,
        schema: type[T],
        timeout_s: float | None,
    ) -> LLMResult[T]:
        result: LLMResult[T] = LLMResult[T](error_code="unsupported_parameters", model_id=model)
        for strategy in self._strategies(model):
            result = self._attempt(model, routing, task, system, user, schema, strategy, timeout_s)
            if result.error_code != "unsupported_parameters":
                return result
            log.info("llm %s: %s rejected the %s strategy, trying the next", task, model, strategy)
        return result

    def _attempt(
        self,
        model: str,
        routing: Sequence[str],
        task: str,
        system: str,
        user: str,
        schema: type[T],
        strategy: Strategy,
        timeout_s: float | None,
    ) -> LLMResult[T]:
        payload = _payload(model, routing, task, system, user, schema, strategy)
        payload["provider"] = {
            **payload.get("provider", {}),
            "data_collection": self.data_collection,
        }
        attempt = 0
        while True:
            try:
                body = self._post(payload, timeout_s)
            except _CallError as failure:
                if failure.retryable and attempt < self.max_retries:
                    attempt += 1
                    self.sleep(min(failure.wait_s, MAX_RETRY_AFTER_S))
                    continue
                if failure.detail:
                    log.warning("llm %s: %s %s: %s", task, model, failure.code, failure.detail)
                return LLMResult[T](error_code=failure.code, model_id=model)
            return _parse(body, schema, strategy, model)

    def _post(self, payload: Mapping[str, Any], timeout_s: float | None) -> Mapping[str, Any]:
        try:
            response = self._client.post(
                "/chat/completions", json=payload, timeout=timeout_s or self.timeout_s
            )
        except httpx.TimeoutException as error:
            raise _CallError("timeout", retryable=True) from error
        except httpx.TransportError as error:
            raise _CallError("unavailable", retryable=True) from error
        status = response.status_code
        if status == 429:
            wait = _retry_after(response.headers.get("Retry-After"))
            raise _CallError("rate_limited", retryable=True, wait_s=wait)
        if status == 402:
            raise _CallError("quota_exhausted")
        if status == 404 or (status == 400 and _mentions_model(response)):
            message, step = _routing_error(response)
            if step is not None and "data policy" in step.casefold():
                raise _CallError("data_policy_refused", detail=message)
            if step is not None and step.casefold().startswith("filter by"):
                raise _CallError("unsupported_parameters", detail=f"{step}: {message}")
            raise _CallError("model_unavailable", detail=message)
        if status >= 500:
            raise _CallError("unavailable", retryable=True)
        if status >= 400:
            raise _CallError("bad_request")
        try:
            body = response.json()
        except ValueError as error:
            raise _CallError("invalid_output") from error
        if isinstance(body, dict) and "error" in body and "choices" not in body:
            # OpenRouter can report an upstream failure with HTTP 200
            raise _CallError("unavailable", retryable=True)
        if not isinstance(body, dict):
            raise _CallError("invalid_output")
        return body

    def _strategies(self, model: str) -> list[Strategy]:
        return strategies_for(self._capabilities().get(model, frozenset()))

    def _capabilities(self) -> Mapping[str, frozenset[str]]:
        if self.capabilities is None:
            self.capabilities = self._fetch_capabilities()
        return self.capabilities

    def _fetch_capabilities(self) -> dict[str, frozenset[str]]:
        try:
            response = self._client.get("/models")
            response.raise_for_status()
            data = response.json().get("data", [])
        except (httpx.HTTPError, ValueError, AttributeError):
            log.warning("could not read OpenRouter model capabilities; using prompt-only JSON")
            return {}
        return {
            str(m["id"]): frozenset(m.get("supported_parameters") or [])
            for m in data
            if isinstance(m, dict) and "id" in m
        }

    # --- cache ------------------------------------------------------------------------

    def _cache_key(
        self, chain: Sequence[str], task: str, system: str, user: str, schema: type[BaseModel]
    ) -> str | None:
        if self.cache_dir is None:
            return None
        material = json.dumps([list(chain), task, schema.__name__, system, user])
        return hashlib.sha256(material.encode()).hexdigest()

    def _cache_read(self, key: str | None, schema: type[T]) -> LLMResult[T] | None:
        if key is None or self.cache_dir is None:
            return None
        path = self.cache_dir / f"{key}.json"
        if not path.is_file():
            return None
        entry = json.loads(path.read_text())
        try:
            parsed = schema.model_validate_json(entry["raw_text"])
        except ValidationError:
            return None
        return LLMResult[T](parsed=parsed, raw_text=entry["raw_text"], model_id=entry["model_id"])

    def _cache_write(self, key: str | None, result: LLMResult[T]) -> None:
        if key is None or self.cache_dir is None or result.parsed is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "model_id": result.model_id,
            "raw_text": result.parsed.model_dump_json(),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        (self.cache_dir / f"{key}.json").write_text(json.dumps(entry))


_NEXT_MODEL_CODES = frozenset(
    {
        "rate_limited",
        "timeout",
        "unavailable",
        "model_unavailable",
        "unsupported_parameters",
        "data_policy_refused",
    }
)


def _payload(
    model: str,
    routing: Sequence[str],
    task: str,
    system: str,
    user: str,
    schema: type[BaseModel],
    strategy: Strategy,
) -> dict[str, Any]:
    json_schema = schema.model_json_schema()
    if strategy is Strategy.PROMPT:
        system = f"{system}\n\n{JSON_ONLY_INSTRUCTION}\n{json.dumps(json_schema)}"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": DEFAULT_MAX_TOKENS.get(task, 600),
        "reasoning": {"exclude": True},
    }
    if len(routing) > 1:
        payload["models"] = list(routing)
    if strategy is Strategy.JSON_SCHEMA:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "strict": True, "schema": json_schema},
        }
        payload["provider"] = {"require_parameters": True}
    elif strategy is Strategy.TOOL:
        payload["tools"] = [
            {
                "type": "function",
                "function": {"name": schema.__name__, "parameters": json_schema},
            }
        ]
        payload["tool_choice"] = {"type": "function", "function": {"name": schema.__name__}}
        payload["provider"] = {"require_parameters": True}
    return payload


def _parse(
    body: Mapping[str, Any], schema: type[T], strategy: Strategy, requested: str
) -> LLMResult[T]:
    model_id = str(body.get("model") or requested)
    try:
        message = body["choices"][0]["message"]
        if strategy is Strategy.TOOL and message.get("tool_calls"):
            raw = str(message["tool_calls"][0]["function"]["arguments"])
        else:
            raw = _FENCE.sub("", str(message.get("content") or "").strip())
            if strategy is Strategy.PROMPT:
                raw = _first_json_object(raw)
    except (KeyError, IndexError, TypeError):
        return LLMResult[T](error_code="invalid_output", model_id=model_id)
    try:
        parsed = schema.model_validate_json(raw)
    except ValidationError:
        return LLMResult[T](error_code="invalid_output", raw_text=raw, model_id=model_id)
    return LLMResult[T](parsed=parsed, raw_text=raw, model_id=model_id)


def _first_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return text
    try:
        _, end = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return text
    return text[start : start + end]


def _retry_after(value: str | None) -> float:
    try:
        return max(float(value), 0.0) if value is not None else 1.0
    except ValueError:
        return 1.0


def _mentions_model(response: httpx.Response) -> bool:
    return "model" in response.text.casefold()


def _routing_error(response: httpx.Response) -> tuple[str, str | None]:
    """OpenRouter's error message and failed routing step (no request data, no key)."""
    try:
        error = response.json().get("error") or {}
    except (ValueError, AttributeError):
        return response.text[:200], None
    metadata = error.get("metadata") or {}
    step = metadata.get("failed_routing_step") if isinstance(metadata, dict) else None
    return str(error.get("message") or "")[:200], step


def strategies_for(params: frozenset[str]) -> list[Strategy]:
    """Output strategies a model supports, best first; prompt-only JSON always comes last."""
    ordered = []
    if "structured_outputs" in params:
        ordered.append(Strategy.JSON_SCHEMA)
    if "tools" in params and "tool_choice" in params:
        ordered.append(Strategy.TOOL)
    return [*ordered, Strategy.PROMPT]


def build_llm(settings: Settings, *, cache: bool = False) -> OpenRouterLLM | None:
    """The configured adapter, or None when LLM paths are disabled or incomplete."""
    if not settings.llm_enabled:
        return None
    if settings.llm_provider != PROVIDER:
        raise ValueError(f"unsupported LLM_PROVIDER {settings.llm_provider!r}")
    if settings.openrouter_api_key is None or settings.llm_model is None:
        log.warning("LLM_PROVIDER is set but OPENROUTER_API_KEY or LLM_MODEL is missing")
        return None
    task_models = {
        task: model
        for task, model in (
            ("query", settings.llm_model_query),
            ("feedback", settings.llm_model_feedback),
            ("descriptions", settings.llm_model_descriptions),
        )
        if model is not None
    }
    return OpenRouterLLM(
        api_key=settings.openrouter_api_key,
        models=[settings.llm_model, *settings.llm_fallback_models],
        base_url=settings.openrouter_base_url,
        task_models=task_models,
        timeout_s=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
        app_title=settings.openrouter_app_title,
        http_referer=settings.openrouter_http_referer,
        cache_dir=settings.llm_cache_dir if cache else None,
        data_collection=settings.llm_data_collection,
    )


@dataclass(frozen=True)
class ModelStatus:
    model_id: str
    exists: bool
    free: bool
    strategy: Strategy | None
    context_length: int | None

    @property
    def ok(self) -> bool:
        return self.exists and self.free and self.strategy in (Strategy.JSON_SCHEMA, Strategy.TOOL)

    @property
    def problem(self) -> str | None:
        if not self.exists:
            return "not listed by OpenRouter (renamed or removed)"
        if not self.free:
            return "no longer free"
        if self.strategy not in (Strategy.JSON_SCHEMA, Strategy.TOOL):
            return "no structured-output or tool support (prompt-only JSON)"
        return None


def model_statuses(
    catalog: Sequence[Mapping[str, Any]], model_ids: Sequence[str]
) -> list[ModelStatus]:
    """Check configured ids against a `GET /models` listing: listed, free, structured output."""
    by_id = {str(m.get("id")): m for m in catalog}
    statuses = []
    for model_id in dict.fromkeys(model_ids):
        m = by_id.get(model_id)
        if m is None:
            statuses.append(ModelStatus(model_id, False, False, None, None))
            continue
        pricing = m.get("pricing") or {}
        free = all(str(pricing.get(k, "1")) in ("0", "0.0") for k in ("prompt", "completion"))
        params = frozenset(m.get("supported_parameters") or [])
        strategy = strategies_for(params)[0]
        statuses.append(ModelStatus(model_id, True, free, strategy, m.get("context_length")))
    return statuses
