# API changelog

The public HTTP contract lives in `src/music_discovery/api/schemas.py`. Its generated forms are
`frontend/openapi.json` and the mock fixtures in `frontend/src/mocks/fixtures/` (regenerate with
`make contract`; `make contract-check` fails when they are stale). Every response carries
`X-API-Version`.

Rules (api-contracts §5): adding optional fields or new endpoints keeps the version; removing or
renaming a field, changing its type or an enum value bumps `API_VERSION` and gets an entry here,
and the UI track is told, because hook return types change.

## API_VERSION 1 — 2026-10-25

First version (P08).

- `GET /api/health`: liveness plus capability status (`semantic`, `llm_interpreter`, `map`) and
  reasons.
- `POST /api/search`: query or follow-up (`session_id`) → `outcome` (`ok`, `no_confident_match`,
  `needs_clarification`), `interpreted_query`, `results` with `score_breakdown` (null = not
  computed), `constraint_status`, `uncertainty_flags`, `spatial`, `capabilities`, `warnings`,
  `change_summary`.
- `GET /api/tracks/{id}`, `GET /api/tracks/{id}/neighbors?k=` (original embedding space;
  `metric` is `clap_cosine` or `catalog_relationship`), `GET /api/tracks/{id}/audio` (licensed
  local clip with Range support).
- `POST /api/feedback` (typed event or free text, optional `refresh`), `GET /api/sessions/{id}`.
- `GET /api/map/points` (keyset pagination, filters) and `GET /api/map/meta`.
- Error envelope `{"error": {"code", "message", "details"}}` on every non-2xx.

Departures from the base.md §13 sketches:

- `artists` are `{artist_id, name}` objects, not bare names.
- Tracks expose `source_url` (the FMA track page) instead of `discogs_url` (ADR-0005).
- Search adds `no_match_reasons`; track details add `related_tracks` and `relationship_counts`.
