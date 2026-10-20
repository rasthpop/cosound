---
name: openrouter-llm
description: The LLM provider for the agents — OpenRouter's free models (https://openrouter.ai/collections/free-models) behind the StructuredLLM protocol. Covers the OpenAI-compatible adapter in infrastructure/llm.py, model configuration and fallback chains, structured-output strategy per model capability, rate-limit/availability handling, data-policy rules for free models, and how models are selected and versioned. Load when writing or changing the LLM adapter, choosing/changing a model, wiring Agent A/C LLM paths, or debugging LLM output validation.
---

# OpenRouter LLM Provider (free models)

**Source of models:** the OpenRouter free collection — https://openrouter.ai/collections/free-models. Free variants have model IDs ending in `:free` (e.g. `nvidia/nemotron-3-super-120b-a12b:free`, `cohere/north-mini-code:free` as listed on 2026-10-20). The collection **changes over time**: models appear, get renamed, or lose their free tier. Never hard-code a model ID in code.

LLMs are **optional** everywhere in this system (base §6, §8): Agent A query interpretation, Agent C free-text feedback normalization, and optional description phrasing. Every LLM path has a deterministic fallback, and the system must run end-to-end with the LLM disabled.

## 1. Configuration

```text
LLM_PROVIDER=openrouter            # empty = LLM paths disabled
OPENROUTER_API_KEY=                # SecretStr; never logged, never committed
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=                         # primary, e.g. <vendor>/<model>:free (chosen in P06.T12)
LLM_FALLBACK_MODELS=               # comma-separated :free models, tried in order
LLM_TIMEOUT_S=20
LLM_MAX_RETRIES=2
OPENROUTER_APP_TITLE=SemanticMusicDiscovery   # sent as X-Title (optional attribution header)
OPENROUTER_HTTP_REFERER=                      # optional HTTP-Referer header
```

Per-task overrides are allowed (`LLM_MODEL_QUERY`, `LLM_MODEL_FEEDBACK`, `LLM_MODEL_DESCRIPTIONS`) and fall back to `LLM_MODEL`.

## 2. Adapter (`infrastructure/llm.py`)

Implements `domain.protocols.StructuredLLM`:

```python
class StructuredLLM(Protocol):
    def generate(self, *, task: str, system: str, user: str,
                 schema: type[BaseModel], timeout_s: float | None = None) -> LLMResult[BaseModel]: ...
# LLMResult: parsed | None, raw_text, model_id (as reported by the response), latency_ms, error_code | None
```

- OpenRouter is **OpenAI-compatible**: use the `openai` SDK with `base_url=OPENROUTER_BASE_URL` (or plain `httpx` to `POST /chat/completions`). Both are allowed only in `infrastructure/` (boundary checker).
- **Fallback chain:** send the primary model with OpenRouter's `models` list (primary + `LLM_FALLBACK_MODELS`) so routing can fall through when a model is unavailable, and also catch errors client-side and try the next model. Record the **model that actually answered** (`response.model`) in `LLMResult.model_id`.
- **Structured output strategy**, chosen per model from its capabilities (query `GET /api/v1/models` at startup or on a cache refresh and read `supported_parameters`):
  1. `structured_outputs` / `response_format` supported → `response_format={"type": "json_schema", "json_schema": {"name": ..., "strict": true, "schema": Model.model_json_schema()}}`, and set provider routing `require_parameters: true` so the request only goes to providers that honor it.
  2. else `tools` supported → a single function tool whose parameters are the schema, with `tool_choice` forcing it.
  3. else → JSON-only instructions in the prompt and extract the first JSON object.
  In **every** case the output is validated with Pydantic. Validation failure → `error_code="invalid_output"`. The adapter never "repairs" content beyond stripping code fences.
- Reasoning models: disable or limit reasoning when the model supports a toggle (e.g. `reasoning: {enabled: false}`) for low-latency tasks. Ignore reasoning text and never show it to users.
- **Errors → codes:** `429` → `rate_limited` (respect `Retry-After`, then next model); `402`/quota → `quota_exhausted`; `5xx`/timeout → `unavailable`; model not found / no longer free → `model_unavailable`. After retries the adapter returns an error result. Raising is reserved for programming errors, so agents can fall back.
- **Circuit breaker:** after N consecutive failures, mark the LLM capability `fallback` for a cooldown period, so searches don't wait on a dead provider. Surface this in `/api/health` and `capabilities.llm_interpreter`.
- Temperature 0 (or the lowest value supported). Fixed `max_tokens` per task.

## 3. Free-tier realities

- **Rate and daily limits apply to free models.** The collection page doesn't state them, so read the current limits in the OpenRouter docs when writing the ADR (P06.T12) and record them with the date. Size the evaluation runs to fit (cache responses, see §5).
- **Data policy:** some free providers state that they may use inputs and outputs for training (the Poolside Laguna pages say so explicitly). Therefore:
  - send only what the task needs: the user's query text, a validated feedback string, or a claim list. Never send API keys, user identifiers, session IDs or catalog dumps;
  - record each chosen model's data policy in the ADR. Prefer models whose providers don't train on inputs when quality is comparable;
  - the account-level privacy settings on OpenRouter may block providers that train on inputs. Document the setting used.
- **Availability churn:** a configured model can disappear. The fallback chain plus the deterministic fallback keep the system working. P06.T12's model check script detects when a model has gone away.

## 4. Prompts

- Live in `src/music_discovery/agents/prompts/*.md` (versioned, with `prompt_version` in front-matter). The adapter is prompt-agnostic.
- Each prompt restates the rules that apply to it: no invented tracks, artists or catalog entries; no claims of instrument detection; soft wording never becomes a hard constraint; output only the schema.
- Use few-shot examples from the lexicon parser's golden cases, **never** from the evaluation test split.

## 5. Reproducibility & evaluation

- Every LLM-derived artifact records `model_id` (as answered), `prompt_version`, `temperature` and a timestamp. `SearchSpecification.interpreter_model` stores it per query.
- Evaluation runs use a **response cache** keyed by `(model_id, prompt_version, input hash)` under `data/llm_cache/` (git-ignored, but snapshotted into the run's artifacts). That makes reruns reproducible and keeps them within free-tier limits. The report lists the exact model IDs and the date they were used, because free models can change behind the same ID.
- Model choice is an evaluated decision (P06.T12). It is compared on the Agent A dev queries by structured-output validity rate, attribute F1, hard-constraint accuracy and p50/p95 latency, against the deterministic parser as the baseline. If no free model beats the deterministic parser, LLM paths stay disabled by default, and that is an acceptable outcome.

## 6. Tests

- Unit tests use `FakeStructuredLLM`. No network calls in the default suite.
- Adapter tests use `httpx.MockTransport` / `respx` against recorded-shape responses for each strategy: json_schema, tool call, prompt-only JSON, 429 with `Retry-After`, model not found → next model, invalid JSON → `invalid_output`, timeout, circuit breaker opening and closing.
- One `@pytest.mark.live` smoke test, skipped without `OPENROUTER_API_KEY`, calls the configured model once with a tiny schema.
