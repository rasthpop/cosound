# U03 — deck.gl Track Map View

**Goal:** the full-bleed "constellation" map from ui.md §4.3, confined to `components/map/`. It is a pure deck.gl renderer of precomputed coordinates: it takes points and emits events, and it never fetches or computes similarity. It comes with its controls, legend, honest caption and accessible fallbacks.
**Depends on:** U01.T03, P09.T02 (U03.T04 legend data also needs P09.T10)

### U03.T01 — Map helpers
- **Skills:** deckgl-track-map
- **Depends on:** U01.T03
- **Files:** frontend/src/components/map/{fitBounds,camera,pointStyle,keys}.ts, frontend/src/components/map/*.test.ts
- **Do:**
  - `fitBounds` for all points (`meta.bounds`) and for a subset (search results) with 80 px padding. Zoom clamped to the projection bounds.
  - Camera transition settings: 600 ms ease-out, or instant under reduced motion.
  - Color/radius/line pickers per point state from `theme/scales`, and stable update-trigger keys for selection, highlight, hover and theme.
- **Done when:**
  - Unit tests: bounds for empty, single point and subset; zoom clamp; reduced-motion duration 0; key stability.
- **Status:** [ ]

### U03.T02 — TrackMap renderer
- **Skills:** deckgl-track-map, ui-architecture
- **Depends on:** U03.T01, P09.T02
- **Files:** frontend/src/components/map/TrackMap.tsx, frontend/src/components/map/TrackMap.test.tsx
- **Do:**
  - `OrthographicView` + `ScatterplotLayer` with props `points`, `selectedTrackIds`, `highlightedTrackIds`, `hoveredTrackId`, `dimUnhighlighted`, `fitTo` (camera request), `onTrackSelect`, `onTrackHover`, `onWebGLError`, `ariaLabel`.
  - Soft additive dots (ui.md §2), controller with inertia, drag/wheel/pinch/double-click and keyboard (arrows pan, `+`/`−` zoom, `0` reset via `onResetRequest`). Memoized layers with stable ids. Points fade in as pages arrive. A visually hidden summary ("Map of N tracks; M results highlighted").
- **Done when:**
  - Component test (deck.gl mocked): a picked click emits `onTrackSelect(track_id)`; updateTriggers change with selection and highlight; `onError` triggers `onWebGLError`. Workbench renders 10k synthetic points (`?mapPoints=10000` generator) smoothly.
- **Status:** [ ]

### U03.T03 — Tooltip, highlight & selection visuals
- **Skills:** deckgl-track-map, ux-states-and-evidence
- **Depends on:** U03.T02
- **Files:** frontend/src/components/map/MapTooltip.tsx, frontend/src/components/map/TrackMap.stories.tsx
- **Do:**
  - The tooltip shows title · artist · genre from `MapPoint` only. The pointer cursor appears on hover. On touch it is a compact card prop for the sheet.
  - Results highlighted (larger + ring) with the rest dimmed; selected = accent ring + slow pulse (none under reduced motion); never color alone.
- **Done when:**
  - Stories: idle field, hover, one selected, results highlighted + others dimmed, reduced motion, 10k points.
- **Status:** [ ]

### U03.T04 — Controls, genre legend, caption & fallbacks
- **Skills:** deckgl-track-map, ux-states-and-evidence
- **Depends on:** U03.T02, P09.T10
- **Files:** frontend/src/components/map/{MapControls,GenreLegend,MapCaption,MapPointList,MapFallback}.tsx, frontend/src/components/map/*.stories.tsx, frontend/src/components/map/*.test.tsx
- **Do:**
  - `MapControls` (bottom-left): zoom ±, reset view, legend toggle, list-alternative toggle, "Only tracks with audio" toggle.
  - `GenreLegend` from `MapMeta.genres` (P08.T11) with counts and scale colors. A click emits `onGenreFilter(genre | null)`. The `null` genre is labeled neutrally. Hidden when `genres` is absent.
  - `MapCaption`, always visible: "Positions come from audio similarity (CLAP + UMAP). Nearness is suggestive, not exact."
  - `MapPointList`: keyboard-navigable list of the same points (also the WebGL fallback).
  - `MapFallback`: "Map is unavailable — search still works."
- **Done when:**
  - Stories: map down, WebGL failure, legend with and without filter, list alternative. axe passes on the list. Tests: legend emits the genre and then `null` on the second click.
- **Status:** [ ]

## Exit criteria
- [ ] deck.gl appears only under `components/map/`; the map never fetches or computes similarity; copy never claims distance = similarity; fallbacks keep the experience usable without the map.
