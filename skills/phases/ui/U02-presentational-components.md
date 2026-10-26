# U02 — Presentational Views & State Variants

**Goal:** every non-map surface in ui.md §4 as a pure component (props in, typed events out) built from shadcn primitives and tokens. Every applicable state from ui.md §6 is a Storybook story fed by contract fixtures, with no backend required.
**Depends on:** U01, P09.T02 (U02.T07 also needs P09.T10)

### U02.T01 — shadcn primitives & formatting helpers
- **Skills:** ui-architecture, ui-design-tokens
- **Depends on:** U01.T04
- **Files:** frontend/src/components/ui/{button,input,badge,tooltip,popover,sheet,drawer,scroll-area,toggle,separator,skeleton}.tsx, frontend/src/components/format/*.ts, frontend/src/components/format/*.test.ts, frontend/src/components/ui/Primitives.stories.tsx
- **Do:**
  - Add the shadcn components from ui.md §8 and restyle them with semantic utilities (glass panel, hairline, accent focus ring). Icons are lucide 16 px / 1.5 stroke.
  - Formatters: artist list, duration, result count ("12 tracks"), and labels for `evidence_status`, `uncertainty_flags`, `constraint_status`, hard-constraint `attribute/operator/value/range`, `vocal_preferences`, neighbor `metric`, `relationship_type`, `error.code`. No percentage formatter exists.
- **Done when:**
  - Primitive stories in both themes pass axe; formatter tests include `null` → absent and unknown enum values (a readable fallback, never invented meaning).
- **Status:** [ ]

### U02.T02 — Search bar, example queries, chips & clarification
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U02.T01
- **Files:** frontend/src/components/search/{SearchBar,ExampleQueries,QueryChips,QueryChip,ClarificationPrompt}.tsx, frontend/src/components/search/*.stories.tsx, frontend/src/components/search/*.test.tsx
- **Do:**
  - `SearchBar` (ui.md §4.1): placeholder copy, Enter/arrow submit (`onQuerySubmit`), Esc blur, indeterminate progress line, stale marker. Example queries are shown when the input is empty and focused, and the copy is passed in as props. A Refine toggle appears when `canRefine`, emitting `onRefineSubmit(text)` (D2).
  - `QueryChips` from `InterpretedQuery`: soft chips get a More/Less menu (`onAttributeFeedback({eventType, attribute, value})`, D1). Hard constraints get a solid outline + lock, read-only, plus an "Edit your search" action (`onEditQuery`). Negatives are struck through or prefixed "not" and read-only. A subtle note appears for `llm_interpreter = "fallback"`, and `uncertainties` are shown as text.
  - `ClarificationPrompt`: the question and a reply field (`onReply`).
- **Done when:**
  - Stories: idle, focused with examples, loading/stale, interpreted soft/hard/negative (`search_ok`, `search_constraint_unknown`), LLM fallback, needs clarification. Tests: emitted payloads typed; hard and negative chips emit no feedback.
- **Status:** [ ]

### U02.T03 — Results panel & rows
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U02.T01
- **Files:** frontend/src/components/results/{ResultsPanel,ResultRow,EvidenceNote,NotOnMapMarker}.tsx, frontend/src/components/audio/MiniPlayer.tsx, frontend/src/components/results/*.stories.tsx, frontend/src/components/results/*.test.tsx
- **Do:**
  - `ResultsPanel` (ui.md §4.2): header with query echo, count and collapse toggle; scroll area; slot for the change strip; empty / no-confident-match / error bodies from U02.T06. On desktop it is the left floating panel. Below 1024 px it is a vaul bottom sheet snapping at 96 px / half / full.
  - `ResultRow`: rank · title · artists · genre/style badges · evidence note (`evidence_status`, `uncertainty_flags`, `retrieval_sources`) · description and `match_reasons` as given · play button only when a playable URL prop is non-null · feedback actions on hover/focus · "not on map" marker. Events: `onTrackSelect(id)`, `onTrackHover(id | null)`, `onFeedback`, `onPlay(id)`.
  - Rows render in prop order, ~56 px tall.
- **Done when:**
  - Stories from fixtures: ok, stale, empty, no confident match, degraded semantic, track without audio, track without coordinates, bottom-sheet snaps (mobile viewport). Tests: order equals input order; no `%` text; null description renders nothing; no link without `source_url`.
- **Status:** [ ]

### U02.T04 — Feedback controls & change strip
- **Skills:** ux-states-and-evidence, ui-architecture
- **Depends on:** U02.T03
- **Files:** frontend/src/components/feedback/{FeedbackActions,InstrumentPicker,ChangeStrip}.tsx, frontend/src/components/feedback/*.stories.tsx, frontend/src/components/feedback/*.test.tsx
- **Do:**
  - `FeedbackActions`: More like this / Less like this / Not relevant, mapped 1:1 to `MORE_LIKE_THIS` / `LESS_LIKE_THIS` / `NOT_RELEVANT`, with per-track pending, rejected (`accepted: false` + `reason`) and error states. Optimistic acknowledgment only.
  - `InstrumentPicker`: popover for `WRONG_INSTRUMENT`, with options from the interpreted query's instruments. It is hidden when there are none.
  - `ChangeStrip`: dismissible list of `change_summary` strings, with the original query kept visible. There is no undo.
- **Done when:**
  - Tests: each gesture emits the right `FeedbackType` and payload; pending/rejected/error render; the strip renders `feedback_refined`.
- **Status:** [ ]

### U02.T05 — Details drawer
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U02.T01, U02.T04
- **Files:** frontend/src/components/track/{TrackDetailsDrawer,NeighborList,RelatedTracks}.tsx, frontend/src/components/audio/AudioPlayer.tsx, frontend/src/components/track/*.stories.tsx, frontend/src/components/track/*.test.tsx
- **Do:**
  - Drawer (ui.md §4.4, ADR-0003): right 400 px non-modal sheet on desktop with Tab looping inside it and Esc/✕ closing it; full-height modal sheet below 1024 px. Contents: title, artists, genres/styles/tags, year, release, duration.
  - Full-width `AudioPlayer` (native `<audio>`) with license + FMA credit next to it, or "No audio preview available."
  - Optional `description` / `match_reasons` props (nothing shown when absent); "Open on FMA" only with `source_url` (`rel="noopener noreferrer"`); feedback actions + instrument picker.
  - `NeighborList` "Nearby in sound" labeled by `metric` (catalog fallback shows its `reason`), with `onTrackSelect` per neighbor. `RelatedTracks` by `relationship_type`.
- **Done when:**
  - Stories: detail, no-audio detail, catalog-fallback neighbors, loading, not found, mobile sheet. axe passes. Test: closing calls `onClose` and the container gets a chance to restore focus.
- **Status:** [ ]

### U02.T06 — State views & status pill
- **Skills:** ux-states-and-evidence
- **Depends on:** U02.T01
- **Files:** frontend/src/components/states/{StatusPill,EmptyState,NoConfidentMatch,ErrorState,OfflineState}.tsx, frontend/src/components/states/*.stories.tsx
- **Do:**
  - `StatusPill` (ui.md §4.5): "Sound-based matching is off — catalog data only", "Map unavailable", "Offline — retry" (`onRetry`). Rendered only when something is degraded.
  - Empty: suggest broadening. No confident match: list `no_match_reasons` and offer "Edit your search" (relaxing is the user's choice, D1). Error: copy by `error.code` with retry, no stack traces. Offline: retry, typed query preserved.
- **Done when:**
  - A story per state; copy checked against `ux-states-and-evidence` (no overclaiming).
- **Status:** [ ]

### U02.T07 — Views for the contract additions (match bands, score bands, structured changes)
- **Skills:** ux-states-and-evidence, ui-architecture
- **Depends on:** U02.T03, U02.T04, U02.T05, P09.T10
- **Files:** frontend/src/components/results/MatchBand.tsx, frontend/src/components/track/ScoreBands.tsx, frontend/src/components/feedback/ChangeStrip.tsx, and their stories/tests
- **Do:**
  - `MatchBand` from `TrackResult.match_strength` ("Strong match" / "Partial match"; `weak` and `null` show no band), used in `ResultRow`.
  - `ScoreBands` (collapsed by default in the drawer) from `score_bands`, with `null` → "not available", never 0.
  - `ChangeStrip` renders structured `changes` (track titles, attributes) when present and falls back to `change_summary` strings.
- **Done when:**
  - Stories from the regenerated fixtures; tests: no number or percentage rendered; `null` band → "not available"; `title: null` falls back to the change string, never the raw track id.
- **Status:** [ ]

## Exit criteria
- [ ] Every non-map surface in ui.md §4 exists as a pure component with all ui.md §6 state stories; `check_boundaries.py --only ts` and the visual-literal check green.
