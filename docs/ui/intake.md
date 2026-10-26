# UI/UX plan intake (U00)

- **Plan:** [`skills/phases/ui/ui.md`](../../skills/phases/ui/ui.md) is the steering document for the interface. It stays where the project owner put it, and every U-phase refers to it by section (`ui.md §4.2`).
- **Contract read against:** `frontend/openapi.json` (API v1, after P09), `frontend/src/hooks/README.md`, `frontend/src/mocks/fixtures/`, and the backend rules in `agents/feedback_rules.py` and `descriptions/evidence_builder.py`.
- **Stack:** [ADR-0003](../adr/0003-ui-stack.md). **Vocabulary:** [glossary](glossary.md).
- **Outputs:** the rewritten `skills/phases/ui/U01–U05`, contract requests appended as P08.T10–T12 and P09.T10–T12, and the decisions in §5.

Legend: ✅ available as a field or event · 🟡 available, needs formatting or joining only (no domain logic) · ❌ missing → see §4.

## 1. Inventory

### Screens and layout zones (ui.md §3)

There is one screen, **Discover** (no router). The map fills the viewport and everything else floats on top of it.

| Zone | Desktop ≥ 1024 px | < 1024 px | Shown when |
|---|---|---|---|
| Map canvas | `fixed inset-0`, behind everything | same | always (calm empty field when unavailable) |
| Search bar + chips | top-center, max 640 px, 24 px from the top | pinned top | always |
| Results panel | left, 380 px, collapsible | bottom sheet, snaps at 96 px / half / full | a plate exists |
| Details drawer | right, 400 px, Esc/✕ closes | full-height sheet over the results sheet | a track is selected |
| Map controls | bottom-left: zoom ±, reset, legend, list alternative, caption | same, compact | always (map available) |
| Status pill | bottom-right | same | only when degraded or offline |

### Interactions

| # | Interaction | Source |
|---|---|---|
| I1 | Submit query (Enter / arrow), `/` focuses the input, Esc blurs it, example queries when empty and focused | §4.1 |
| I2 | Progress line while searching; previous plate stays, marked stale | §4.1, §6 |
| I3 | Interpreted-query chips: soft, hard (lock), negative (strikethrough/"not"); a chip action sends feedback | §4.1 |
| I4 | Clarification question + reply field | §4.1 |
| I5 | Refine toggle: follow-up text goes to free-text feedback instead of a new search | §9 |
| I6 | Results rows in API order; hover → map highlight; click → select (fly-to + drawer) | §4.2 |
| I7 | Row feedback on hover/focus: More / Less like this, Not relevant | §4.2 |
| I8 | Inline mini-player, one track at a time | §4.2 |
| I9 | "What changed" strip after feedback, dismissible; original query stays visible | §4.2 |
| I10 | Map pan/zoom (drag, wheel, pinch, double-click, inertia, clamped to bounds) | §4.3 |
| I11 | Map hover tooltip; click selects (same state as a row click); camera eases | §4.3 |
| I12 | Search highlight: results lit, the rest dimmed, camera fits the results (80 px, 600 ms) | §4.3 |
| I13 | Reset view (`0` key) fits all points and clears the highlight but keeps the list | §4.3 |
| I14 | Genre legend: click filters the map by genre, click again resets; "only with audio" toggle | §4.3 |
| I15 | Map keyboard: arrows pan, `+`/`−` zoom; list alternative (`MapPointList`) | §4.3, §7 |
| I16 | Details drawer: player, description, reasons, collapsible score bands, neighbors (click → select), FMA link, feedback incl. "Wrong instrument…" | §4.4 |
| I17 | Status pill: semantic off / map off / offline + retry | §4.5 |
| I18 | Free browse: no query, click any point → drawer | §5.5 |

### Visual system (ui.md §2), encoded as tokens in U01

Dark-first `#0B0B0F` canvas, plus an optional light mode that changes tokens only · map points 2–4 px at ~0.55 opacity, additive · 8–10 desaturated genre hues + a neutral grey for `null` genre (`fma_small` has 8 top genres) · highlight 6–8 px with a ring, others at ~0.15 · selection = accent ring + slow pulse (no pulse under reduced motion) · glass panels `rgba(18,18,24,0.72)` + blur 12 px, hairline border, radius 12–16 px · Inter Variable, sizes 13/15/20/28, weights 400/500 · one accent (violet `#A78BFA` default) for focus, selection and the primary action only · lucide 16 px / 1.5 stroke · motion 150–250 ms ease-out, 600 ms camera · 8 px grid, ~56 px rows.

The plan's visual reference (Subwave, "See the shape of your library") could not be fetched when the plan was written. U01.T01 checks the reference and adjusts **token values only**.

### Accessibility & platform (ui.md §7)

Full keyboard path (`/` → input → results → feedback → details → map list) · `aria-live="polite"` for result counts and refinements · focus trapped in the drawer and returned on close · WCAG AA on translucent panels over the map · selection never shown by color alone · `prefers-reduced-motion`. Targets: evergreen desktop browsers and touch tablets/phones (< 1024 px layout). WebGL failure falls back to the list.

### Technology preferences (ui.md §8)

shadcn/ui (Radix) · Tailwind v4 · deck.gl · vaul · lucide-react · motion · native `<audio>` · @fontsource-variable/inter · Storybook or Ladle. ADR-0003 makes the final choices.

## 2. Element → data mapping

### Search bar & interpreted query (§4.1)

| Element | Data / event | |
|---|---|---|
| Submit query | `useMusicSearch().search(text)`; follow-ups reuse the session | ✅ |
| Progress line / stale marker | `status === "loading"`, `isRefreshing` | ✅ |
| Example queries | static copy in `pages/` | ✅ |
| Soft chips (instrument, mood, genre, energy, tempo, texture, era) | `interpreted_query.*_preferences[]` → `Preference.value` (`weight` is not shown as a number) | ✅ |
| Vocals chip | `interpreted_query.vocal_preferences` (enum label; `unspecified` → no chip) | 🟡 |
| Hard-constraint chips (lock) | `interpreted_query.hard_constraints[]` (`attribute`, `operator`, `value`/`range`) | 🟡 label |
| Negative chips | `interpreted_query.negative_preferences[]` | ✅ |
| Chip "less of this" | `submit({eventType: "LESS_OF_ATTRIBUTE", attribute: category, value})` | ✅ (meaning: see D1) |
| Chip "remove" (×) | no event removes a preference without turning it into a negative | ❌ → D1 |
| Hard-constraint removal | feedback never drops a hard constraint (Agent C invariant) | ❌ → D1 (conflict) |
| Clarification text | `outcome === "needs_clarification"`, `clarification_question` | ✅ |
| Clarification reply | `search(reply)` in the same session (Agent A refines the session's spec) | ✅ |
| Refine toggle (free text) | `submit({freeText}, {refresh: true})` | ✅ (D2) |
| LLM fallback note | `capabilities.llm_interpreter === "fallback"`; `warnings[code=llm_fallback]` | ✅ |
| Interpreter uncertainties | `interpreted_query.uncertainties[]` (shown as text) | ✅ |

### Results panel (§4.2)

| Element | Data / event | |
|---|---|---|
| Query echo | `interpreted_query.original_query` (or `lastQuery`) | ✅ |
| Result count "12 tracks" | `results.length` | 🟡 |
| Row order | `results[]` in API order, `rank` | ✅ |
| Title · artists | `title`, `artists[].name` joined | 🟡 |
| Genre/style badges | `genres[]`, `styles[]` | ✅ |
| Match strength band | only free text in `match_reasons` ("Strong semantic match", "Partial audio match"); no structured band | ❌ → P08.T10 |
| Evidence note | `evidence_status`, `uncertainty_flags[]` (`no_audio`, `vocals_unknown`, …), `retrieval_sources[]` (no `semantic` → "Matched on catalog data only") | 🟡 enum labels |
| Constraint status | `constraint_status[]` (`satisfied`/`unknown`/…) | 🟡 label |
| Description / reasons | `description` (null → nothing), `match_reasons[]` | ✅ |
| Play button | `preview_url` non-null; the API path must be resolved to a playable URL, and `pages/` cannot import `api/client` | ❌ → P09.T12 |
| Feedback actions | `useTrackFeedback().submit({trackId, eventType})`, `isPending(id)`, `byTrack[id].error`, `response.accepted/reason` | ✅ |
| Row hover → map highlight | container UI state → `TrackMap.hoveredTrackId` | ✅ |
| Row click → select | `useMusicMap().select(id)` (+ `SELECT_TRACK` when the track is in the plate) | ✅ |
| "Not on map" marker | `spatial === null`, or `spatial.projection_version !== useMusicMap().projectionVersion` | 🟡 |
| "What changed" strip | `FeedbackResponse.change_summary[]` / `refreshed.change_summary[]`; entries name tracks by **id** (`"excluded trk_example_1"`) | ❌ → P08.T12 |
| Empty / no confident match | `results=[]` + `outcome="ok"`; `outcome="no_confident_match"` + `no_match_reasons[]` | ✅ |
| Error | `error.code`, `error.kind` (`ApiError`) | ✅ |

### Map (§4.3)

| Element | Data / event | |
|---|---|---|
| Points | `useMusicMap().points` (`x`, `y`, `track_id`), loaded page by page | ✅ |
| Point color | `MapPoint.genre` → `theme/scales/categorical`; `null` → neutral token | ✅ |
| Legend entries (stable, unfiltered, with counts) | not in `MapMeta`; deriving them from loaded points breaks once a genre filter is applied and while pages are still loading | ❌ → P08.T11 |
| Legend click → filter | `setFilters({genre})` / `resetFilters()` | ✅ |
| "Only with audio" | `setFilters({has_audio: true})` | ✅ |
| Bounds / zoom clamp / reset | `meta.bounds` | ✅ |
| Tooltip | `MapPoint.title`, `artist`, `genre` | ✅ |
| Click → select | `select(id)`; `SELECT_TRACK` only with an active search (otherwise the hook answers `no_active_search` without a request) | ✅ |
| Search highlight + fit | `results[].track_id` ∩ `points`, camera fitted to their `x/y` (view geometry only) | 🟡 |
| Selection ring | `selectedTrackIds` | ✅ |
| Unavailable | `availability === "unavailable"`, `meta.reason`, `error.code` | ✅ |
| WebGL failure | deck.gl `onError` (view-local) | ✅ |
| Caption | static copy | ✅ |
| Points fade in | `status`, `isLoadingMore`, `hasMore` | ✅ |

### Details drawer (§4.4)

| Element | Data / event | |
|---|---|---|
| Title, artists, genres, styles, tags, year, release | `useTrackDetails(id).detail` | ✅ |
| Duration | `detail.duration_seconds` / `audio.duration_seconds` (null → absent) | 🟡 |
| License + FMA credit | `detail.audio.license` + static attribution copy ("via the Free Music Archive", CC BY 4.0 dataset credit) | 🟡 |
| Player / "No audio preview available." | `detail.preview_url` (needs URL resolution) | ❌ → P09.T12 |
| Description, match reasons, score bands | not in `TrackDetail`: they come from the `TrackResult` with the same `track_id` in the current plate, so tracks opened from the map show none | 🟡 join + ❌ bands → P08.T10 |
| Neighbors "Nearby in sound" | `neighbors.neighbors[]`, `metric` (`clap_cosine` vs labeled `catalog_relationship` fallback + `reason`) | ✅ |
| Neighbor click → select | `useMusicMap().select(neighbor.track_id)` | ✅ |
| Related tracks (same artist/album) | `detail.related_tracks[]`, `relationship_type` | ✅ |
| "Open on FMA" | `detail.source_url` (null → no link) | ✅ |
| Feedback incl. "Wrong instrument…" | `submit({trackId, eventType: "WRONG_INSTRUMENT", attribute: "instrument", value})`; picker options = `interpreted_query.instrument_preferences` (hidden when empty) | ✅ |
| Loading / not found / no audio | `status`, `error.code === "track_not_found"`, `audio_available` | ✅ |

### Status pill (§4.5)

| Element | Data / event | |
|---|---|---|
| Semantic off | `data.capabilities.semantic` after a search; before the first search only `GET /api/health`, which no hook exposes | ❌ → P09.T11 |
| Map off | `useMusicMap().availability` | ✅ |
| Offline + retry | `error.kind === "network"` (+ `navigator.onLine`), `refresh()` / `search(lastQuery)` | ✅ |

## 3. States (ui.md §6) → fixture / scenario

| State | Fixture | Scenario (`?scenario=`) | |
|---|---|---|---|
| idle | — | any | ✅ |
| loading / refreshing (stale) | — | `slow-network` | ✅ |
| ok | `search_ok` | `happy` | ✅ |
| empty | `search_empty` | none | ❌ → P09.T10 (`empty`) |
| no confident match | `search_no_confident_match` | `no-confident-match` | ✅ |
| needs clarification | `search_needs_clarification` | `needs-clarification` | ✅ |
| degraded semantic | `search_semantic_unavailable`, `health_degraded` | `degraded-semantic` | ✅ |
| degraded map | `map_unavailable`, `error_map_unavailable` | `map-down` | ✅ |
| LLM fallback | `search_llm_fallback` | none | ❌ → P09.T10 (`llm-fallback`) |
| error | `error_*` | `errors` | ✅ |
| offline | — (network failure, not an HTTP error) | none | ❌ → P09.T10 (`offline`) |
| WebGL failure | — (view-local) | — | ✅ story only |
| track without audio | `track_detail_no_audio`, `neighbors_no_audio`, `search_ok[2]` | `happy` | ✅ |
| track without coordinates | `search_ok[2]` (`spatial: null`) | `happy` | ✅ |
| constraint unknown | `search_constraint_unknown` | none | ✅ (story from fixture) |

## 4. Gap analysis

| Gap | Kind | Resolution |
|---|---|---|
| G1 Structured match band per result (and per signal for the details breakdown) | contract | **P08.T10** adds `match_strength` (`strong`/`partial`/`weak`/`null`) and `score_bands` to `TrackResult`, computed by the existing `SemanticBands` logic server-side. The UI never buckets `score`, and doesn't parse `match_reasons` strings. |
| G2 Stable genre legend with counts | contract | **P08.T11** adds `MapMeta.genres: [{genre: string \| null, count}]` for the whole projection, independent of filters and pagination. |
| G3 "What changed" names tracks by id | contract | **P08.T12** keeps `change_summary` strings for compatibility and adds structured `changes[]` (`kind`, `track_id`, `title`, `attribute`, `value`) with titles resolved server-side. |
| G4 Types, fixtures, scenarios for G1–G3, plus `empty`, `llm-fallback`, `offline` scenarios | contract | **P09.T10** |
| G5 Capabilities before the first search | contract | **P09.T11** `useSystemStatus()` over the existing `GET /api/health` (`client.health()`). |
| G6 Playable preview URL in `pages/` | contract | **P09.T12** exports `useMediaUrl(path)` (or `resolveMediaUrl`) from `hooks/`, so views and containers never import `api/client`. |
| G7 Chip ✕ "remove", hard-constraint removal | conflict | **D1** below. |
| Cluster/region labels on the map (ui.md §9) | out of MVP | No request, as the plan says. Only the genre legend. |
| Enum labels, artist joining, durations, result count, "not on map", legend colors, fit-to-results camera | presentation | U02.T01 formatters, U03 helpers. |
| Description/reasons for a track opened from the plate | presentation (join by id) | U04.T04: the container passes the matching `TrackResult` to the drawer. |

Until G1, G2 and G3 land, the views render without them: no band badge, a legend built only from `meta` (hidden when `genres` is absent), and the raw `change_summary` strings. They never fall back to client-side derivation. The U-tasks that consume them depend on P09.T10.

## 5. Decisions

Under the skill's rule, the functional rule applies until the project owner decides otherwise. The defaults below are what U02/U04 implement, and the PR review is where they get confirmed or changed.

- **D1 (conflict). Chip removal.** The plan maps chip ✕ to `LESS_OF_ATTRIBUTE`. Agent C lowers the weight by 0.2 and only turns the preference into a *negative* once it drops below 0.2. Hard constraints are never dropped by feedback (that request is rejected). **Default:** soft chips get a small menu "More of this" (`MORE_OF_ATTRIBUTE`) / "Less of this" (`LESS_OF_ATTRIBUTE`) and no ✕. Hard-constraint chips are read-only with a lock, plus the hint "Edit your search to change this", which prefills the input with `original_query`. That is also how "relax constraints" works in the no-confident-match state. Negative chips are read-only. **Open for the owner:** a neutral `REMOVE_ATTRIBUTE` feedback type (P06 + P08 + P09 change) if a true ✕ is wanted.
- **D2. Refine toggle (ui.md §9).** The plan's proposal is adopted. With a plate on screen, a "Refine" toggle next to the input sends the text as `submit({freeText}, {refresh: true})`. It is off by default, so Enter runs a new search in the same session. No contract change.
- **D3. Match band source (ui.md §9).** No structured field exists, so P08.T10 adds one (G1).
- **D4. Map click without a search.** It opens details only. `SELECT_TRACK` is sent only when a session exists (the backend records it, and the spec doesn't change).
- **D5. Workbench.** Storybook (ADR-0003).

## 6. Verification

`python skills/implementation-roadmap/scripts/phase_status.py --check` and `python skills/music-discovery-architecture/scripts/check_boundaries.py` pass with the appended tasks. U00 adds no code.
