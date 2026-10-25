# P09 — Frontend Data Layer: Types, Client, Mocks & Hooks

**Goal:** the functional half of the frontend — generated types, a typed API client, contract mocks, and four hooks — so that any visual interface can search, show a plate, submit feedback, and get map points **without implementing ML or retrieval logic** (Milestone 6). This phase defines the seam the UI track builds on; it contains no visual decisions.
**base.md:** §14.1–14.3, §16 (stale frontend requests).
**Depends on:** P08.T07 (contract), P00.T04 (frontend skeleton)

### P09.T01 — Generated types & contract check
- **Skills:** api-contracts, ui-architecture
- **Depends on:** P08.T07, P00.T04
- **Files:** frontend/src/api/generated.ts, frontend/src/api/types.ts, frontend/package.json (contract:check)
- **Do:**
  - `openapi-typescript` generation; `types.ts` re-exports friendly aliases only (`SearchRequest`, `SearchResponse`, `TrackResult`, `TrackDetail`, `FeedbackRequest`, `FeedbackResponse`, `FeedbackType`, `MapPoint`, `MapPointsResponse`, `MapMeta`, `NeighborsResponse`, `ApiError`, …).
  - `npm run contract:check` regenerates and fails on diff; added to CI.
- **Done when:**
  - Typecheck passes; editing a backend DTO without regenerating fails CI.
- **Notes:** Generation via `frontend/scripts/contract.mjs` (openapi-typescript API, alphabetized, banner) instead of the CLI, so `--check` compares in-memory output with the committed file. openapi-typescript 7.13 declares a TypeScript ^5 peer; an npm `overrides` entry lets it use the project's TS 6 (it only uses the printer). Chain: backend test fails if `openapi.json` is stale; frontend CI `contract:check` fails if `generated.ts` is stale. `make contract`/`contract-check` now cover all three artifacts. `types.ts` holds aliases plus the client-only `ApiError`.
- **Status:** [x]

### P09.T02 — Contract mocks (MSW) & mock dev mode
- **Skills:** ui-isolated-development, api-contracts
- **Depends on:** P09.T01
- **Files:** frontend/src/mocks/{handlers,scenarios,browser,server}.ts, frontend/src/mocks/fixtures/ (from P08.T07), frontend/src/mocks/generateMapPoints.ts, frontend/.env.mock
- **Do:**
  - Handlers for every endpoint per scenario (`happy`, `degraded-semantic`, `map-down`, `no-confident-match`, `needs-clarification`, `slow-network`, `errors`); scenario switch via query param; synthetic large map dataset generator; `npm run dev:mock`.
- **Done when:**
  - Every handler response type-checks against `types.ts`; vitest server setup with `onUnhandledRequest: "error"`.
  - **Unblocks UI track** (U02, U03).
- **Notes:** Fixtures are typed through `mocks/fixtures.ts` (JSON imports widen enum strings, so each fixture is bound to its DTO alias; a test checks the binding equals the backend's `fixtures/index.json`). Handlers type-check derived bodies via a `json<T>()` helper. Happy handlers echo session ids, issue `qry_mock_N` ids, paginate a fixed point list (or `?mapPoints=N` synthetic points); free-text-only feedback answers `feedback_rejected`; `artist_id` is ignored by the mock (map points carry no artist id). `main.tsx` starts the worker only when `VITE_API_MODE=mock`; the production bundle contains no MSW code (only the inert `mockServiceWorker.js` is copied from `public/`).
- **Status:** [x]

### P09.T03 — API client
- **Skills:** api-contracts, ui-architecture
- **Depends on:** P09.T01
- **Files:** frontend/src/api/client.ts, frontend/src/api/client.test.ts
- **Do:**
  - Base URL from env; typed functions per endpoint; `AbortSignal` support; JSON (de)serialization; error normalization to `ApiError {code, message, status, details, kind: "http"|"network"|"aborted"|"parse"}`; no business rules.
- **Done when:**
  - Tests via MSW: success, envelope error, network error, abort, malformed JSON.
- **Notes:** `createApiClient({baseUrl, fetch})` + default `apiClient`; failures throw `ApiClientError` (implements `ApiError`, with `toJSON()`); `resolveUrl()` turns `preview_url` paths into absolute URLs. Generation now uses `defaultNonNullable: false`: openapi-typescript otherwise marks request fields with server defaults (`limit`, `refresh`) as required.
- **Status:** [x]

### P09.T04 — `useMusicSearch`
- **Skills:** ui-architecture, ui-isolated-development
- **Depends on:** P09.T03, P09.T02
- **Files:** frontend/src/hooks/useMusicSearch.ts, frontend/src/hooks/useMusicSearch.test.tsx
- **Do:**
  - `search(query, {limit})`, `refresh()`, `applyRefreshed(response)`; exposes `status` (`idle|loading|success|error`), `data` (full `SearchResponse` incl. outcome/capabilities/warnings), `error`, `sessionId`, `queryId`; cancels in-flight request on new search; stale-response protection via request sequence; keeps previous data during refinement (`isRefreshing`).
- **Done when:**
  - Tests: out-of-order responses never overwrite newer; abort on unmount; session id retained across searches; refresh after feedback.
- **Notes:** `search()` resolves to the response or `null` (failed/superseded) so callers can chain. `refresh()` re-sends the last query text in the same session; the backend reads it as a follow-up with nothing new, so the plate reflects the session's current (feedback-updated) spec. Also `reset()` and `search(q, {newSession: true})`. Errors keep the last good plate; aborts never surface as errors. Shared `RequestStatus` in `hooks/status.ts`.
- **Status:** [x]

### P09.T05 — `useTrackFeedback`
- **Skills:** ui-architecture
- **Depends on:** P09.T04
- **Files:** frontend/src/hooks/useTrackFeedback.ts, frontend/src/hooks/useTrackFeedback.test.tsx
- **Do:**
  - `submit({trackId, eventType, attribute?, value?, freeText?}, {refresh})` using current session/query ids from `useMusicSearch` (passed in, not global); per-track submission state; returns `FeedbackResponse`; pushes refreshed plate into `useMusicSearch`.
- **Done when:**
  - Tests: accepted/rejected flows, per-track pending state, refresh propagates, invalid event surfaces `ApiError`.
- **Notes:** Takes `{sessionId, queryId, applyRefreshed}` from `useMusicSearch`. State per track id, or `PLATE_KEY` for track-less free text; `isPending(trackId)`, `lastResponse`. `accepted: false` is a successful response, not an error. Submitting before any search records a client-side `no_active_search` error (no request is sent). Pending requests abort on unmount.
- **Status:** [x]

### P09.T06 — `useTrackDetails`
- **Skills:** ui-architecture
- **Depends on:** P09.T03
- **Files:** frontend/src/hooks/useTrackDetails.ts, frontend/src/hooks/useTrackDetails.test.tsx
- **Do:**
  - Fetch details (+ optional neighbors) by id; in-memory cache keyed by id with invalidation on `projection_version` change; loading/error states; abort on id change.
- **Done when:**
  - Tests: cache hit avoids request, id switch aborts previous, 404 surfaces typed error.
- **Notes:** Cache is per hook instance, held in state (no setState-in-effect, no ref reads during render, as React Hooks v7 requires); loading is derived from "no entry yet". `projectionVersion` (from useMusicMap) scopes the cache. A failed neighbors call keeps the details (`neighborsError`); `reload()` drops the entry and refetches.
- **Status:** [x]

### P09.T07 — `useMusicMap`
- **Skills:** ui-architecture, deckgl-track-map
- **Depends on:** P09.T03
- **Files:** frontend/src/hooks/useMusicMap.ts, frontend/src/hooks/useMusicMap.test.tsx
- **Do:**
  - Fetch meta + paginated points (auto or `loadMore`), filters (genre/style/artist_id/has_audio) with reset, `projectionVersion`, availability state, `selectedTrackIds` + `select/deselect/clear` callbacks; **no deck.gl import, no coordinate or similarity computation**.
- **Done when:**
  - Tests: full pagination walk, filter change resets, version change resets, map-down scenario exposes `unavailable`, selection callbacks.
- **Status:** [ ]

### P09.T08 — Hook contract documentation (the UI seam)
- **Skills:** ui-architecture, implementation-roadmap
- **Depends on:** P09.T04, P09.T05, P09.T06, P09.T07
- **Files:** frontend/src/hooks/README.md, frontend/src/hooks/index.ts
- **Do:**
  - Document each hook's signature, return shape, states, events, and the scenario fixtures that exercise them; single `index.ts` export surface that the UI track imports from.
- **Done when:**
  - README matches the TS signatures (spot-checked by `api-contract-guardian`); UI track can implement containers from this document alone.
- **Status:** [ ]

### P09.T09 — Contract harness (dev-only, unstyled) — M6 acceptance
- **Skills:** ui-architecture, ui-isolated-development
- **Depends on:** P09.T08
- **Files:** frontend/src/dev/ContractHarness.tsx, frontend/src/dev/README.md, frontend/e2e/contract-harness.spec.ts
- **Do:**
  - A deliberately plain, unstyled dev page (served only at `/__dev/harness`, excluded from production build) that uses the four hooks to: search, list the plate as raw fields, submit each feedback type, list map points with pagination. It is **not** the UI — no design decisions, deleted or kept dev-only once U04 exists.
  - Playwright test runs it in mock mode, and (optionally, `slow`) against the real backend.
- **Done when:**
  - E2E test proves search → plate → feedback → refreshed plate → map points with zero ML/retrieval logic in the frontend.
- **Status:** [ ]

## Exit criteria (Milestone 6)
- [ ] The interface layer can search, display a plate, submit feedback, and retrieve map points without implementing ML or retrieval logic (P09.T09).
- [ ] Loading, error, empty, degraded, and stale-response states exposed by hooks and tested.
- [ ] `contract:check` and boundary check green.
