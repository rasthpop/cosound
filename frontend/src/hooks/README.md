# hooks/: the seam between the functional system and any interface

Four hooks give a visual layer everything it needs to search, show a plate, send feedback,
open track details and draw the map. They hold **no** ranking, retrieval, ML or coordinate
logic: the backend decides relevance and positions, and the hooks only fetch, cancel, cache
and expose state.

```ts
import { useMusicSearch, useTrackFeedback, useTrackDetails, useMusicMap } from "@/hooks";
import type { TrackResult, MapPoint, FeedbackType } from "@/api/types";
```

Rules for containers (`src/pages/`, the only place hooks are called):

- Show results in API order. Never re-sort, filter or score them.
- Missing values are `null`. Render them as absent, never as 0 or "".
- `error` values are `ApiError` objects: `{kind: "http" | "network" | "aborted" | "parse", code, message, status, details}`.
  `code` is the server's stable error code (e.g. `track_not_found`). Aborted requests never
  surface as errors.
- `RequestStatus` is `"idle" | "loading" | "success" | "error"`.
- Every hook takes an optional `client` (from `createApiClient`); tests and the mock mode use
  the default client against MSW.

Scenarios to build every state against: `npm run dev:mock` and `?scenario=<name>`, with the
names `happy`, `degraded-semantic`, `map-down`, `no-confident-match`,
`needs-clarification`, `slow-network` and `errors`. `?mapPoints=10000` serves a synthetic map.
Fixtures live in `src/mocks/fixtures/`.

---

## `useMusicSearch(options?) → MusicSearch`

The current plate and its session.

Options: `{ client?, limit? }`. `limit` is the default plate size.

| Field | Type | Meaning |
|---|---|---|
| `status` | `RequestStatus` | state of the latest request |
| `data` | `SearchResponse \| null` | the latest plate, kept while a newer request loads or after it fails |
| `error` | `ApiError \| null` | why the latest request failed |
| `sessionId` | `string \| null` | session of `data` |
| `queryId` | `string \| null` | query of `data` (what feedback refers to) |
| `lastQuery` | `string \| null` | text of the last search sent |
| `isRefreshing` | `boolean` | loading while an older plate is still shown |
| `search` | `(query, {limit?, newSession?}?) => Promise<SearchResponse \| null>` | runs a search; resolves `null` if it failed or was superseded |
| `refresh` | `() => Promise<SearchResponse \| null>` | re-runs the last search in the same session; the plate then reflects feedback sent without `refresh` |
| `applyRefreshed` | `(response: SearchResponse) => void` | shows a plate obtained elsewhere (`useTrackFeedback` calls it) |
| `reset` | `() => void` | forgets the plate and the session |

Behavior:
- A new `search` cancels the request in flight. A response that arrives after a newer one
  started is dropped, so a stale plate never overwrites a newer one.
- The session id is reused by the next `search`, so follow-ups refine the same session. Pass
  `{newSession: true}` or call `reset()` to start over.
- Outcomes that are not errors arrive as `status: "success"` with `data.outcome`:
  - `ok`, possibly with an empty `results`;
  - `no_confident_match`, with `data.no_match_reasons`;
  - `needs_clarification`, with `data.clarification_question`.
- Degraded modes are also data: `data.capabilities` (`semantic`, `llm_interpreter`, `map`) and
  `data.warnings` (`semantic_unavailable`, `llm_fallback`, `map_unavailable`, …).

Fixtures: `search_ok`, `search_empty`, `search_no_confident_match`,
`search_needs_clarification`, `search_semantic_unavailable`, `search_llm_fallback`,
`search_constraint_unknown`.

## `useTrackFeedback(search, options?) → TrackFeedback`

Feedback on the current plate. `search` is the `useMusicSearch` result (only `sessionId`,
`queryId` and `applyRefreshed` are used). Options: `{ client? }`.

| Field | Type | Meaning |
|---|---|---|
| `submit` | `(input: FeedbackInput, {refresh?, limit?}?) => Promise<FeedbackResponse \| null>` | sends one event; `null` if the request failed |
| `byTrack` | `Record<string, FeedbackState>` | `{status, error, response}` per track id; `PLATE_KEY` for feedback without a track |
| `isPending` | `(trackId?) => boolean` | that track's submission is in flight |
| `lastResponse` | `FeedbackResponse \| null` | the most recent response |

`FeedbackInput` is `{ trackId?, eventType?, attribute?, value?, freeText? }`, where
`eventType` is a `FeedbackType`:

- `MORE_LIKE_THIS`, `LESS_LIKE_THIS`, `NOT_RELEVANT`, `WRONG_INSTRUMENT` and `SELECT_TRACK`
  need `trackId`;
- `MORE_OF_ATTRIBUTE`, `LESS_OF_ATTRIBUTE` and `WRONG_INSTRUMENT` need `attribute`;
- free text alone (`freeText`, no `eventType`) is allowed.

`SELECT_TRACK` may name any catalog track, e.g. a point clicked on the map.

Behavior:
- With `{refresh: true}`, the refreshed plate in the response is pushed into `useMusicSearch`
  (`applyRefreshed`).
- `response.accepted === false` (with `response.reason`) is a successful call: the backend
  understood the request but nothing changed.
- Server-side validation errors (unknown session or track, track not in results, …) surface in
  `byTrack[id].error`. Sending feedback before any search gives `code: "no_active_search"`
  without a request.
- `response.change_summary` says what changed; `response.next_action` is `REFINE_SEARCH`,
  `SHOW_DETAILS` or `NONE`.

Fixtures: `feedback_refined`, `feedback_rejected`, `error_track_not_in_results`.

## `useTrackDetails(trackId, options?) → TrackDetailsState`

Details of one track, plus its neighbors if asked. `trackId: null` means idle.

Options: `{ client?, withNeighbors?, k?, projectionVersion? }`.

| Field | Type | Meaning |
|---|---|---|
| `status` | `RequestStatus` | `idle` without an id |
| `detail` | `TrackDetail \| null` | metadata, release, audio info, related tracks, `spatial` |
| `neighbors` | `NeighborsResponse \| null` | only with `withNeighbors` |
| `error` | `ApiError \| null` | e.g. `track_not_found` (404) |
| `neighborsError` | `ApiError \| null` | neighbors failed while the details loaded |
| `reload` | `() => void` | drops the cached entry and refetches |

Behavior:
- Results are cached by id, so going back to a track sends no request.
- Pass the map's `projectionVersion`: when it changes, the cache is dropped.
- Changing `trackId` aborts the previous request.
- Neighbors come from the original audio-embedding space (`metric: "clap_cosine"`), or a
  labeled catalog fallback (`metric: "catalog_relationship"`, with `reason`). They are not map
  distances.
- `detail.preview_url` is the audio clip's API path, or `null`. Turn it into a URL with the
  API client's `resolveUrl`.

Fixtures: `track_detail`, `track_detail_no_audio`, `neighbors`, `neighbors_no_audio`,
`error_track_not_found`.

## `useMusicMap(options?) → MusicMap`

Map data for any renderer. The map view receives `points` and emits selection events. The
hook never imports deck.gl and never computes coordinates or similarity.

Options: `{ client?, pageSize?, autoLoad?, maxPoints?, enabled?, initialFilters? }`. The
defaults are a page size of 500, `autoLoad: true` and `enabled: true`.

| Field | Type | Meaning |
|---|---|---|
| `availability` | `"loading" \| "available" \| "unavailable" \| "error"` | `unavailable` = the backend has no usable projection (search still works) |
| `meta` | `MapMeta \| null` | projection version, bounds, counts |
| `status` | `RequestStatus` | state of the first page of points |
| `points` | `readonly MapPoint[]` | points loaded so far, in API order |
| `projectionVersion` | `string \| null` | version of `points` |
| `hasMore` | `boolean` | more pages exist |
| `isLoadingMore` | `boolean` | a `loadMore()` call is running |
| `error` | `ApiError \| null` | e.g. `projection_unavailable` |
| `loadMore` | `() => Promise<void>` | next page (when `autoLoad` is false or stopped at `maxPoints`) |
| `filters` | `MapFilters` | `{genre?, style?, artist_id?, has_audio?}` |
| `setFilters` | `(filters: MapFilters) => void` | restarts from the first page |
| `resetFilters` | `() => void` | back to `initialFilters` |
| `reload` | `() => void` | refetches meta and points |
| `selectedTrackIds` | `ReadonlySet<string>` | selection (kept across filter changes) |
| `select` / `deselect` / `toggle` | `(trackId: string) => void` | selection changes |
| `clearSelection` | `() => void` | empties the selection |

Behavior:
- If a page arrives from a different projection version than the points already loaded,
  everything resets, so points from two maps never mix.
- Map coordinates are for visualization only and are not a similarity measure. Neighbors come
  from `useTrackDetails`.

Fixtures: `map_meta`, `map_points_page1`, `map_points_page2`, `map_unavailable`,
`error_map_unavailable`.
