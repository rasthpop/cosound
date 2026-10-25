# P08 — Application Services & FastAPI

**Goal:** thin, validated HTTP transport over application services, with a stable public contract (OpenAPI + fixtures) that the frontend data layer and the UI track build against.
**base.md:** §13, §16, §17 (API tests), §3.
**Depends on:** P06.T10, P07.T05, P07.T06

> P08.T02 (DTOs + examples) and P08.T07 (OpenAPI/fixtures export) can be started early, right after P06.T10's shapes stabilize, to unblock P09.T01–T02 and the UI track.

### P08.T01 — Application services & capability status
- **Skills:** api-contracts, agent-orchestration, music-discovery-architecture
- **Depends on:** P06.T10, P07.T05, P07.T06
- **Files:** src/music_discovery/application/{search_service,feedback_service,track_service,capabilities}.py, tests/unit/application/*.py
- **Do:**
  - `SearchService.search/refine`, `FeedbackService.submit` (validation + optional refresh), `TrackService.get/neighbors`, `CapabilityService` (semantic / llm / map availability probes, cached; llm reflects the OpenRouter circuit-breaker state).
  - Services return domain results; no HTTP concepts.
- **Done when:**
  - Unit tests with fakes for each service, including degraded capabilities and invalid feedback references.
- **Notes:** Added `application/results.py` (`TrackView` = track + validated audio + coordinates) shared by all services, and a domain `InvalidRequest` error (code `validation_error`). Follow-up queries go through `SearchService.search(session_id=…)` (Agent A decides refinement); feedback-driven re-search lives in `FeedbackService`. Accepted spec-changing feedback always records the new turn; `refresh` only decides whether the plate is returned. Capabilities are cached 5 s; `llm_interpreter` reads `OpenRouterLLM.status` (circuit breaker). Test world in `tests/support/world.py` (real agents, in-memory fakes).
- **Status:** [x]

### P08.T02 — Public DTOs, mapping & examples
- **Skills:** api-contracts, domain-modeling
- **Depends on:** P06.T10
- **Files:** src/music_discovery/api/schemas.py, src/music_discovery/api/mapping.py, tests/api/test_schemas.py
- **Do:**
  - DTOs per the api-contracts skill (base §13 shapes + outcome, capabilities, warnings, constraint_status, uncertainty_flags, spatial, change_summary). ADR-0005: expose `source_url` (FMA track page) instead of `discogs_url`; mapping functions domain → DTO; `json_schema_extra` examples covering every outcome/degraded variant.
- **Done when:**
  - Mapping tests: nulls preserved, enums correct, no domain/ORM object leaks; every example validates.
- **Notes:** `artists` are `{artist_id, name}` objects (not bare names as in the base §13.1 sketch) so the UI can filter the map by artist. Search adds `no_match_reasons`; track details expose `related_tracks` (capped per type) + `relationship_counts`. Examples live in `api/examples.py` (fictional `trk_example_*` placeholders, no real links), keyed by the fixture names T07 exports, and are attached to each DTO's JSON schema.
- **Status:** [x]

### P08.T03 — App factory, composition root & error envelope
- **Skills:** api-contracts, music-discovery-architecture
- **Depends on:** P08.T01, P08.T02
- **Files:** src/music_discovery/api/app.py, src/music_discovery/api/dependencies.py, src/music_discovery/api/errors.py, src/music_discovery/api/routes/health.py, tests/api/test_errors.py
- **Do:**
  - `create_app(settings)`; DI wiring settings → infrastructure → services (lazy CLAP load, graceful failure); exception handlers mapping domain error codes → status + envelope; replace default 422 body; CORS from settings; request id + structured access logs; `GET /api/health`.
  - `make serve` → `uvicorn music_discovery.api.app:create_app --factory`.
- **Done when:**
  - Tests: each error code → expected status/envelope; app starts with CLAP checkpoint missing (semantic unavailable) and with projection missing (map unavailable).
- **Notes:** `create_app(settings, services=…)` lets tests inject services built over fakes (`tests/support/world.py`); routes read them via `api/dependencies.get_*`. Startup degrades instead of failing: no embeddings → `embeddings_unavailable`, embeddings but no checkpoint → `clap_checkpoint_missing` (neighbors still use the index), bad/missing projection → map unavailable. Unmapped domain codes and unexpected exceptions return a generic 500 envelope. Added `infrastructure/ids.py` (`RandomIdGenerator`).
- **Status:** [x]

### P08.T04 — Search, track & neighbor routes
- **Skills:** api-contracts
- **Depends on:** P08.T03
- **Files:** src/music_discovery/api/routes/search.py, src/music_discovery/api/routes/tracks.py, tests/api/test_search.py, tests/api/test_tracks.py
- **Do:**
  - `POST /api/search`, `GET /api/tracks/{id}`, `GET /api/tracks/{id}/neighbors`; limit bounds; outcome variants.
- **Done when:**
  - API tests: schema, invalid input, empty results, metadata-only results, semantic unavailable warning, needs-clarification, no-confident-match, invalid track id 404.
- **Notes:** `limit` 1–100 (Agent B's bound), `k` 1–50; violations are 422 envelopes, blank queries too. Stable `operation_id`s (`search`, `getTrack`, `getTrackNeighbors`) for generated client types.
- **Status:** [x]

### P08.T05 — Feedback & session routes
- **Skills:** api-contracts, agent-orchestration
- **Depends on:** P08.T03
- **Files:** src/music_discovery/api/routes/feedback.py, src/music_discovery/api/routes/sessions.py, tests/api/test_feedback.py
- **Do:**
  - `POST /api/feedback` (typed events + optional free text; optional `refresh=true` returns refreshed plate), `GET /api/sessions/{id}`.
- **Done when:**
  - API tests: unknown session/query/track, track not in results (409), SELECT_TRACK from map, refresh changes results, history visible in session.
- **Notes:** Typed event or `free_text` alone (normalized by the lexicon/optional LLM, else `accepted=false` with a reason). Status codes: unknown session/track 404, query not in session / track not in results / stale session version 409, malformed event 422 (`invalid_feedback_event` or `validation_error`).
- **Status:** [x]

### P08.T06 — Map routes
- **Skills:** api-contracts, umap-spatial-projection
- **Depends on:** P08.T03
- **Files:** src/music_discovery/api/routes/map.py, tests/api/test_map.py
- **Do:**
  - `GET /api/map/points` (limit/cursor/genre/style/artist_id/has_audio), `GET /api/map/meta`.
- **Done when:**
  - API tests: pagination walk returns every point once, filters, limit cap, projection unavailable ⇒ 503 envelope while `/api/search` still 200.
- **Status:** [ ]

### P08.T07 — OpenAPI & fixture export
- **Skills:** api-contracts, ui-isolated-development
- **Depends on:** P08.T02
- **Files:** scripts/export_openapi.py, scripts/export_fixtures.py, frontend/openapi.json, frontend/src/mocks/fixtures/*.json, tests/api/test_fixtures_valid.py, docs/api-changelog.md
- **Do:**
  - Deterministic OpenAPI JSON (sorted keys, stable operation ids); fixtures for every scenario listed in `ui-isolated-development`; test validating each fixture against its DTO; changelog started at `API_VERSION=1`.
- **Done when:**
  - Re-running both scripts produces no git diff; fixture test green.
- **Status:** [ ]

### P08.T08 — API robustness suite
- **Skills:** api-contracts
- **Depends on:** P08.T04, P08.T05, P08.T06
- **Files:** tests/api/test_degraded_modes.py, tests/integration/test_api_end_to_end.py
- **Do:**
  - Agent failure (LLM invalid output) ⇒ 200 with fallback; CLAP load failure ⇒ metadata-only with warning; stale/duplicate feedback; large limit rejected; end-to-end against the real small index.
- **Done when:**
  - All base §17 "API tests" bullets have at least one test; end-to-end test green under `integration`.
- **Status:** [ ]

### P08.T09 — Licensed audio preview endpoint
- **Skills:** api-contracts, fma-audio-corpus
- **Depends on:** P08.T04
- **Files:** src/music_discovery/api/routes/audio.py, src/music_discovery/application/track_service.py, tests/api/test_audio.py
- **Do:**
  - `GET /api/tracks/{track_id}/audio` streams the track's local FMA clip (HTTP range requests, correct content type) only when a validated `TrackAudio` record exists; `preview_url` in DTOs points to it, and stays `null` otherwise.
  - Paths are resolved only from `TrackAudio.file_path` under `DATA_DIR` (no user-supplied paths; refuse anything that escapes it). The response carries the track's license.
- **Done when:**
  - API tests: valid track streams, range request returns 206, track without audio returns 404 envelope, path traversal impossible, license header present.
- **Status:** [ ]

## Exit criteria (Milestone 6, backend)
- [ ] Search, track details, neighbors, feedback, sessions, map points/meta exposed with validated schemas.
- [ ] Error envelope everywhere; degraded modes visible in responses.
- [ ] `frontend/openapi.json` + fixtures generated, deterministic, validated.
