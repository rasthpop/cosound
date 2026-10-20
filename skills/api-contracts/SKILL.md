---
name: api-contracts
description: The public HTTP contract between backend and interface — FastAPI thin routes, request/response DTOs, error envelope and codes, degraded-mode and outcome fields, OpenAPI export, generated TypeScript types, fixture parity, and the contract-change procedure. Load when touching src/music_discovery/api/, any response/request schema, frontend/src/api/types.ts or generated.ts, frontend/src/mocks/, or whenever the UI needs data the API doesn't yet provide.
---

# API Contracts

Spec: `base.md` §13, §14.1–14.2, §16. **This contract is the seam that keeps the visual interface isolated from the functional system.** Both sides depend on it; neither depends on the other.

## 1. Layering

```
route (api/routes/*.py)  →  application service  →  agents / retrieval / spatial
   ↑ DTO in/out (api/schemas.py)        ↑ domain objects
```

- Routes: parse DTO → call one application service method → map result to DTO. No business logic, no repository access, no try/except except via the shared exception handler.
- `api/schemas.py` holds DTOs (`SearchRequest`, `SearchResponse`, `TrackResult`, `TrackDetail`, `FeedbackRequest`, `FeedbackResponse`, `MapPointsResponse`, `NeighborsResponse`, `ErrorResponse`). **Never** return domain or ORM models directly.
- `api/dependencies.py` is the composition root (settings → infrastructure → services), cached per app; tests override with fakes via `app.dependency_overrides`.

## 2. Endpoints (base §13, with the additions the rest of the plan requires)

| Method & path | Purpose |
|---|---|
| `POST /api/search` | query → plate |
| `GET /api/tracks/{track_id}` | details, links, audio availability, relationships, coordinates |
| `GET /api/tracks/{track_id}/neighbors?k=` | original-space neighbors |
| `POST /api/feedback` | feedback → updated state (+ optionally refreshed plate) |
| `GET /api/sessions/{session_id}` | session state & history ("what changed") |
| `GET /api/map/points?limit&cursor&genre&style&artist_id&has_audio` | paginated coordinates |
| `GET /api/map/meta` | projection_version, bounds, counts, availability |
| `GET /api/health` | liveness + capability status (semantic, llm, map) |

### Required additions to base §13 shapes

`SearchResponse` gains (all always present):

```json
{
  "outcome": "ok | no_confident_match | needs_clarification",
  "clarification_question": null,
  "capabilities": {"semantic": "available | unavailable", "llm_interpreter": "used | fallback | disabled", "map": "available | unavailable"},
  "warnings": [{"code": "semantic_unavailable", "message": "…"}],
  "interpreted_query": { "...full public view of SearchSpecification incl. weights, hard_constraints, negative_preferences..." },
  "results": [ { "...": "...", "score_breakdown": {"semantic": 0.84, "metadata": null, "relationship": null},
                 "constraint_status": [{"attribute": "vocals", "status": "unknown"}],
                 "uncertainty_flags": ["no_audio"], "spatial": {"x": -2.4, "y": 1.8, "projection_version": "umap-…"} } ]
}
```

`FeedbackResponse`: `{accepted, reason?, updated_search_state, change_summary: [str], next_action: "REFINE_SEARCH|SHOW_DETAILS|NONE", refreshed?: SearchResponse}`.

Rules:
- Missing stays `null` (base §13.1). No fabricated `preview_url`/`discogs_url`.
- `score` fields are relevance scores in [0,1] **for ordering**, documented as not probabilities.
- Enum values are UPPER_SNAKE for event types (as in base), lower_snake elsewhere; never change an enum value without a version bump.

## 3. Errors

Single envelope for every non-2xx:

```json
{"error": {"code": "track_not_found", "message": "Track trk_… does not exist.", "details": {}}}
```

Mapping from `domain.errors` codes: `validation_error`→422, `*_not_found`/`session_not_found`→404, `track_not_in_results`/`query_not_in_session`→409, `contradictory_constraints`→422, `projection_unavailable`/`semantic_unavailable` (only when an endpoint *requires* it)→503, unknown→500 (message generic, details logged server-side). FastAPI's default 422 body is replaced by the envelope.

## 4. OpenAPI → TypeScript

```bash
uv run python scripts/export_openapi.py > frontend/openapi.json           # deterministic, sorted keys
cd frontend && npx openapi-typescript openapi.json -o src/api/generated.ts
```

- `frontend/src/api/types.ts` re-exports friendly aliases from `generated.ts` (`export type SearchResponse = components["schemas"]["SearchResponse"]`) and holds **no hand-written shapes** that duplicate the schema.
- CI/`make contract-check`: regenerate both files and `git diff --exit-code` — schema drift fails the build.
- Every DTO has `json_schema_extra` examples; `scripts/export_fixtures.py` writes them to `frontend/src/mocks/fixtures/*.json`, and an API test asserts each fixture validates against the live schema. UI work builds against these fixtures (see `ui-isolated-development`).

## 5. Contract-change procedure

1. Change DTO + mapping + API tests (backend).
2. Regenerate `openapi.json`, `generated.ts`, fixtures; fix `types.ts` aliases and hooks.
3. If a field is removed/renamed: bump `API_VERSION` header, note in `docs/api-changelog.md`, and flag the UI track (hooks' return types changed).
4. UI requests for new data: the UI track files a task in P08/P09 ("contract request") — the UI never derives data from other fields to work around a missing one.

## 6. Tests (`tests/api/`)

TestClient with dependency overrides: schema of every endpoint, invalid input → envelope, empty results, metadata-only/no-audio results, semantic-unavailable degraded response, agent failure → fallback still 200, invalid track IDs, feedback validation (unknown session/query/track), map pagination & filters, map unavailable → 503 while search still 200.
