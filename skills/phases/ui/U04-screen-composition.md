# U04 — Containers & the Discover Screen

**Goal:** wire the hooks to the views in the single Discover screen (ui.md §3, §5). The map is the canvas, and search, results and details float on it. Selecting in the list and on the map is one event. Containers own only UI state.
**Depends on:** U02, U03, P09.T08, P09.T11, P09.T12

### U04.T01 — Discover screen layout & search wiring
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U02.T02, U02.T03, U02.T06, P09.T04, P09.T08, P09.T11
- **Files:** frontend/src/pages/DiscoverPage.tsx, frontend/src/pages/layout.tsx, frontend/src/pages/copy.ts, frontend/src/pages/useShortcuts.ts, frontend/src/pages/DiscoverPage.test.tsx
- **Do:**
  - Layout zones and breakpoints from ui.md §3 (map `fixed inset-0`; floating bar, panel, drawer, controls, pill; bottom sheets below 1024 px).
  - `useMusicSearch` → bar, chips, clarification (reply = follow-up `search`), results panel and states. `useSystemStatus` + search capabilities + `useMusicMap().availability` → status pill (retry = `reload` / `refresh`).
  - Shortcuts: `/` focuses the input, Esc. An `aria-live="polite"` region announces "N results for …". Example-query copy lives in `copy.ts`. Flow 1 (idle): full map, input focused, examples visible.
- **Done when:**
  - MSW-backed tests for happy, empty, no-confident-match, needs-clarification, degraded-semantic, llm-fallback, offline and error scenarios; the live region announces the result count.
- **Status:** [ ]

### U04.T02 — Feedback & refinement wiring
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U04.T01, U02.T04, P09.T05
- **Files:** frontend/src/pages/DiscoverPage.tsx, frontend/src/pages/feedback.ts, frontend/src/pages/feedback.test.tsx
- **Do:**
  - Row and drawer gestures and chip More/Less (D1) → `useTrackFeedback.submit(..., {refresh: true})`. Refine toggle (D2) → `submit({freeText}, {refresh: true})`. "Edit your search" prefills the input with `original_query`.
  - Per-track pending, rejected and error states. The change strip shows the response and the live region announces the refinement. The map highlight follows the refreshed plate (flow 4).
- **Done when:**
  - E2E (mock): 👎 on a row gives a refreshed plate, a visible "what changed" and an updated highlight; a rejected feedback shows its reason; hard-constraint chips send nothing.
- **Status:** [ ]

### U04.T03 — Map container & selection sync
- **Skills:** ui-architecture, deckgl-track-map
- **Depends on:** U04.T01, U03.T03, U03.T04, P09.T07
- **Files:** frontend/src/pages/MapLayer.tsx, frontend/src/pages/selection.ts, frontend/src/pages/MapLayer.test.tsx
- **Do:**
  - `useMusicMap` → `TrackMap`. Highlight = result ids with coordinates in the current `projectionVersion`, and the camera fits them on a new plate. The rest are "not on map" in the list.
  - Hover cross-highlights rows ⇄ points. A click on either selects through one `selectTrack(id)` (`useMusicMap.select`, drawer opens, camera eases; `SELECT_TRACK` only with an active session, D4). Reset clears the highlight but keeps the list.
  - Legend → `setFilters({genre})` / `resetFilters()`, the audio toggle → `has_audio`. WebGL error → list alternative. Map down → fallback, search unaffected. Free browse (flow 5) opens the drawer with the results panel hidden.
- **Done when:**
  - E2E (mock): a map click opens details; a row click selects the point; search results highlight and the rest dim; `map-down` leaves search fully usable.
- **Status:** [ ]

### U04.T04 — Details drawer container
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U02.T05, U02.T07, P09.T06, P09.T12
- **Files:** frontend/src/pages/DetailsLayer.tsx, frontend/src/pages/audio.ts, frontend/src/pages/DetailsLayer.test.tsx
- **Do:**
  - `useTrackDetails(selectedId, {withNeighbors: true, projectionVersion})` → drawer. The matching `TrackResult` from the current plate is joined by `track_id` for description, reasons and bands (absent for tracks opened from the map).
  - `useMediaUrl` → players, with one track playing at a time across rows and drawer. A neighbor click → `selectTrack`. Focus returns to the originating row or point on close.
- **Done when:**
  - Tests: open/close focus behavior; neighbor click selects that track and moves the camera; a no-audio track shows "No audio preview available."; a second play pauses the first.
- **Status:** [ ]

### U04.T05 — App shell & the dev harness
- **Skills:** ui-architecture
- **Depends on:** U04.T01, U04.T03, U04.T04, P09.T09
- **Files:** frontend/src/App.tsx, frontend/src/main.tsx, frontend/src/App.test.tsx, frontend/src/dev/README.md
- **Do:**
  - `App` = `ThemeProvider` + `DiscoverPage`. No router. `/__dev/harness` stays dev-only.
- **Done when:**
  - The production build contains neither the harness nor MSW (existing check); all container tests and e2e pass.
- **Status:** [ ]

## Exit criteria
- [ ] Hooks are called only in `pages/`; views remain pure; display order equals API order; list and map selection are one event; search works with the map down.
