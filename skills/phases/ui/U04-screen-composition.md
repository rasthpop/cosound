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
- **Status:** [x]
- **Notes:** `DiscoverLayout` places the zones with Tailwind `lg` (1024 px). `useIsDesktop` picks the results panel or the vaul sheet, and defaults to desktop without `matchMedia`. Esc is left to the views (SearchBar blurs, the drawer closes); `useShortcuts` ignores single-key shortcuts while a field has focus. The pill merges the plate's capabilities (else health's) with `useMusicMap().availability`; its retry reloads health and the map, and re-runs an offline search. A small `ResultsLoading` view (row skeletons) was added to `ResultsPanel.tsx` for the first search. Chip feedback is a no-op until T02, and the map slot is an empty canvas until T03.

### U04.T02 — Feedback & refinement wiring
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U04.T01, U02.T04, P09.T05
- **Files:** frontend/src/pages/DiscoverPage.tsx, frontend/src/pages/feedback.ts, frontend/src/pages/feedback.test.tsx
- **Do:**
  - Row and drawer gestures and chip More/Less (D1) → `useTrackFeedback.submit(..., {refresh: true})`. Refine toggle (D2) → `submit({freeText}, {refresh: true})`. "Edit your search" prefills the input with `original_query`.
  - Per-track pending, rejected and error states. The change strip shows the response and the live region announces the refinement. The map highlight follows the refreshed plate (flow 4).
- **Done when:**
  - E2E (mock): 👎 on a row gives a refreshed plate, a visible "what changed" and an updated highlight; a rejected feedback shows its reason; hard-constraint chips send nothing.
- **Status:** [x]
- **Notes:** `App` now renders `DiscoverPage` (moved from T05, because the mock E2E needs the page at `/`). `ChangeStrip` gained `status`/`message`, so a rejected refinement shows the backend's `reason` and a failed one its error. A row's own failures stay on the row (`FeedbackActions`). Seeing the page in a browser showed the row's feedback column squeezing the title column, so `ResultRow` now puts its actions under the text (a status keeps them visible), and `InstrumentPicker` has an icon-only `compact` trigger for rows. On small screens the status pill sits under the search instead of overlapping the chips. Tests: `pages/feedback.test.tsx` (MSW) and `e2e/discover.spec.ts`. The map-highlight part of the E2E comes with T03.

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
- **Status:** [x]
- **Notes:** `MapLayer.tsx` exports `useMapLayer`, which returns `{canvas, controls}` because the layout puts them in different zones. It owns the legend/list toggles, zoom requests and the WebGL-failure flag. `DiscoverPage` owns selection, hover, the highlight and the camera requests. `selectTrack` sets the drawer's id and the map selection and eases the camera; it sends `SELECT_TRACK` only with a session (D4), through a second `useTrackFeedback` instance so a selection never appears as a row's feedback status. The results fit and the selection use the *drawn* point's coordinates and fall back to `result.spatial`: in the fixtures they differ (trk_example_1 is at (-0.6, 0.3) on the map but (-0.5, 0.25) in the result), and fitting to the result's coordinates would miss the dots. "Map down" covers `availability` `unavailable` and `error`. `TrackMap` got `pickingRadius` 6 px (the dots are 2–4 px). `ResultRow` got `hovered` for the cross-highlight. The legend starts collapsed beside the desktop results panel, which it otherwise squeezes, until the user toggles it. The E2E clicks a real canvas point under reduced motion, placed with `fitBounds`.

### U04.T04 — Details drawer container
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U02.T05, U02.T07, P09.T06, P09.T12
- **Files:** frontend/src/pages/DetailsLayer.tsx, frontend/src/pages/audio.ts, frontend/src/pages/DetailsLayer.test.tsx
- **Do:**
  - `useTrackDetails(selectedId, {withNeighbors: true, projectionVersion})` → drawer. The matching `TrackResult` from the current plate is joined by `track_id` for description, reasons and bands (absent for tracks opened from the map).
  - `useMediaUrl` → players, with one track playing at a time across rows and drawer. A neighbor click → `selectTrack`. Focus returns to the originating row or point on close.
- **Done when:**
  - Tests: open/close focus behavior; neighbor click selects that track and moves the camera; a no-audio track shows "No audio preview available."; a second play pauses the first.
- **Status:** [x]
- **Notes:** `audio.ts` enforces one clip at a time at the document level: a capture-phase `play` listener pauses every other `<audio>`. `AudioPlayer` marks its element with `data-player="details"`, so the page can clear the row's playing state when the drawer starts. Focus returns to the row or button the selection came from; canvas picks return focus to the map region (`onPointSelect`); a neighbor clicked inside the drawer keeps the original origin. Drawer feedback and score bands appear only for tracks in the current plate. A failed neighbors request hides the section instead of leaving a skeleton. In-browser fixes: the drawer's labeled feedback actions now wrap instead of overflowing, and on desktop the floating zones make room for the open drawer (`lg:pr-52`) so it never covers the search button. Story tests weren't re-run after the last view tweaks (FeedbackActions, AudioPlayer).

### U04.T05 — App shell & the dev harness
- **Skills:** ui-architecture
- **Depends on:** U04.T01, U04.T03, U04.T04, P09.T09
- **Files:** frontend/src/App.tsx, frontend/src/main.tsx, frontend/src/App.test.tsx, frontend/src/dev/README.md
- **Do:**
  - `App` = `ThemeProvider` + `DiscoverPage`. No router. `/__dev/harness` stays dev-only.
- **Done when:**
  - The production build contains neither the harness nor MSW (existing check); all container tests and e2e pass.
- **Status:** [x]
- **Notes:** The App switch landed in T02. The "existing check" was manual, so it is now `scripts/check-bundle.mjs`, which runs at the end of `npm run build` (and therefore in CI). It fails on MSW setup, mock-scenario code, the harness, or `mockServiceWorker.js`, and it does flag a `--mode mock` build. The worker was in fact being copied into production `dist/` from `public/`; a `drop-mock-worker` plugin in `vite.config.ts` now removes it from non-mock builds. `App.test.tsx` covers the Discover screen at `/` and the harness at `/__dev/harness` in development.

## Exit criteria
- [x] Hooks are called only in `pages/`; views remain pure; display order equals API order; list and map selection are one event; search works with the map down.
