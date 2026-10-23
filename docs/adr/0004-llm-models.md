# ADR-0004: Free LLM models for the agents (OpenRouter)

- **Status:** Accepted (project owner, 2026-10-23)
- **Date:** 2026-10-23
- **Phase/Task:** P06.T12; affects P06.T03 (query), P06.T09 (feedback), P06.T06 (descriptions), P08

## Context

Agents A and C can optionally use an LLM. Agent A uses it for query interpretation, Agent C to
normalize free-text feedback, and the description service to rephrase descriptions. Each path
has a tested deterministic fallback, and the system runs end to end with the LLM disabled
(`LLM_PROVIDER` empty). base.md and the `openrouter-llm` skill limit us to OpenRouter's free
models, so the choice has to account for their limits, data policies and churn.

### Shortlist (checked 2026-10-23)

These came from `GET https://openrouter.ai/api/v1/models`. On that date it listed 468 models,
17 of them `:free`. I kept the free models that support structured outputs or forced tool
calls (`supported_parameters`), with a healthy endpoint, from different providers.

| Model id | Provider (endpoint) | Context | Output strategy | Endpoint on 2026-10-23 |
|---|---|---|---|---|
| `google/gemma-4-31b-it:free` | Google AI Studio | 262,144 | json_schema (`response_format`, tools) | up (100 % 30 min) |
| `xingchen-agi/xing4.0-29b-a4b:free` | Phala | 262,144 | json_schema (`structured_outputs`) | up |
| `dots-studio/dots-3-note-preview:free` | AtlasCloud | 512,000 | json_schema (`structured_outputs`) | up |
| `nvidia/nemotron-3-super-120b-a12b:free` | Nvidia | 262,144 | json_schema (`structured_outputs`) | **down** (status -5) |
| `google/gemma-4-26b-a4b-it:free` | Google AI Studio | 262,144 | json_schema (`response_format`, tools) | up |

Excluded:
- `poolside/laguna-*`: their model pages say Poolside may use inputs and outputs for training
  (recorded in the `openrouter-llm` skill on 2026-10-20; not re-read for this ADR).
- Tool-only models without `tool_choice` (`thinkingmachines/inkling*`): tool use can't be forced.
- `nvidia/nemotron-3.5-content-safety`: a classifier, with no tools or structured outputs.
- `liquid/lfm-2.5-2.6b`: its endpoint was down, and at 2.6B it is a small model.

### Free-tier limits (OpenRouter docs, "API rate limits", read 2026-10-23)

- 20 requests per minute on `:free` models.
- 50 requests per day for accounts with less than 10 credits bought in total; 1,000 per day
  with at least 10 credits.
- 429 responses carry `X-RateLimit-*` headers and, when the provider gives one, `Retry-After`.
  The adapter honours it, capped at 10 s, then moves to the next model.
- A negative balance can return 402 even for free models. The adapter maps that to
  `quota_exhausted` and stops the chain.

At 50 requests per day, one Agent A comparison run is 10 dev queries × 5 models = 50 calls,
which is the whole daily quota. Responses are cached under `data/llm_cache/`, so a rerun costs
nothing.

### Data policy

Neither the models API nor the model pages (they render client-side) gave a machine-readable
training or retention policy for these endpoints. **Not verified:** the owner checks each chosen
model's provider policy in the OpenRouter UI before enabling it. Independently of that:

- The OpenRouter account's privacy settings (https://openrouter.ai/settings/privacy) should
  **block providers that train on inputs** for free models (there are separate free/paid
  settings). With that set, OpenRouter does not route to such providers.
- Independently of the account setting, every request sends `provider.data_collection: "deny"`
  (`LLM_DATA_COLLECTION`, default `deny`, added 2026-10-23), so OpenRouter routes only to
  providers that do not store or train on user data. A model with no such provider is refused
  (404); the adapter moves to the next model, then to the deterministic path. Setting it to
  `allow` requires a decision recorded here.
- Each task sends only what it needs: the query text, the feedback text, or the claim list. No
  keys, user or session identifiers, or catalog data are sent (base §3 non-negotiables; enforced
  in `agents/llm_query_interpreter.py`, `agents/feedback_text.py` and
  `descriptions/llm_phrasing.py` and covered by tests).

### Evaluation

`scripts/llm_model_check.py --evaluate` runs the 10 Agent A dev queries through each candidate
(prompt `query-v1`, temperature 0, cached). It reports the LLM-acceptance (validity) rate,
attribute micro F1, hard-constraint accuracy and p50/p95 latency next to the deterministic
parser. **It has not been run:** there is no `OPENROUTER_API_KEY` on the development machine.

The deterministic baseline on the same queries (run `p06-agents-dev`, 2026-10-23) has micro
F1 1.000, hard-constraint accuracy 1.000, vocals accuracy 1.000 and validity 1.000. The
lexicon was written against these labels, so that score shows consistency rather than
generalization. But it means no model can *beat* the baseline on the evaluation set. At best a
model ties it, while adding latency, free-tier limits and a data-policy question.

## Decision

1. **LLM paths stay disabled by default** (`LLM_PROVIDER` empty, `default_enabled: false` in
   `config/llm.yaml`). The skill names this as an acceptable outcome when no free model beats
   the deterministic parser.
2. When the owner opts in, the per-task model chains are those in `config/llm.yaml`:
   - query: `google/gemma-4-31b-it:free` → `xingchen-agi/xing4.0-29b-a4b:free` →
     `dots-studio/dots-3-note-preview:free`;
   - feedback and descriptions: `google/gemma-4-31b-it:free` →
     `xingchen-agi/xing4.0-29b-a4b:free`.

   Gemma 4 31B is primary because it supports both `response_format` and forced tool calls
   (two output strategies), its endpoint is from a large provider with stable uptime, and it
   is the largest healthy dense model on the list. This is a judgment from the listing, not a
   measured result.
3. Description phrasing stays off even when the LLM is on (`LLM_DESCRIPTIONS=false`), because
   the template text already passes the claim validator by construction.
4. `scripts/llm_model_check.py` is run before enabling and periodically. It warns when a
   configured model is no longer listed, no longer free, or loses structured-output support.
   `--strict` fails on models configured in `.env`.

## Consequences

- No user-facing behavior depends on a free model's availability, limits or data policy.
- Agent A and Agent C evaluations measure the deterministic paths; the LLM columns stay empty
  (`llm_acceptance_rate: null`).
- To enable: set `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, and `LLM_MODEL` /
  `LLM_FALLBACK_MODELS` (or `LLM_MODEL_QUERY` …) from `config/llm.yaml`. Then run
  `scripts/llm_model_check.py --strict --evaluate` and record the comparison here.
- Free models change behind the same id: every LLM-derived spec records `interpreter_model`, and
  evaluation reports list the model ids and dates used.

## Open items

- [x] Owner accepts "disabled by default" (2026-10-23).
- [ ] Owner checks each chosen model's data policy on OpenRouter and sets the account to block
      training providers for free models.
- [ ] With a key: run `scripts/llm_model_check.py --evaluate`, add the table to this ADR.
