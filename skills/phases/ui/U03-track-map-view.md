# U03 — deck.gl Track Map View *(provisional)*

**Goal:** a pure deck.gl renderer of precomputed coordinates with selection/hover events, result highlighting, accessible fallbacks, and the UI plan's visual treatment — confined to `components/map/`.
**Depends on:** U01.T03, P09.T02

### U03.T01 — Map helpers
- **Skills:** deckgl-track-map
- **Depends on:** U01.T03
- **Files:** frontend/src/components/map/{fitBounds,pointStyle,keys}.ts(+tests)
- **Do:**
  - Fit-to-bounds view state, color/radius/line pickers from theme scales, stable update-trigger keys for selection/highlight/theme.
- **Done when:**
  - Unit tests for bounds (incl. single point, empty), key stability.
- **Status:** [ ]

### U03.T02 — TrackMap renderer
- **Skills:** deckgl-track-map, ui-architecture
- **Depends on:** U03.T01, P09.T02
- **Files:** frontend/src/components/map/TrackMap.tsx, frontend/src/components/map/TrackMap.test.tsx
- **Do:**
  - `OrthographicView` + `ScatterplotLayer` per the skill; props contract (`points`, `selectedTrackIds`, `highlightedTrackIds`, `onTrackSelect`, `onTrackHover`); controller options and visual treatment from the UI plan; memoized layers.
- **Done when:**
  - Component test: click on picked object emits `onTrackSelect(track_id)`; updateTriggers change with selection; renders 10k synthetic points smoothly in the workbench.
- **Status:** [ ]

### U03.T03 — Hover/tooltip & selection visuals
- **Skills:** deckgl-track-map, ux-states-and-evidence
- **Depends on:** U03.T02
- **Files:** frontend/src/components/map/MapTooltip.tsx, frontend/src/components/map/*.stories.tsx
- **Do:**
  - Tooltip content from point fields only; selected/highlighted/dimmed treatments (not color-only); honest labeling of what map proximity means.
- **Done when:**
  - Stories: none selected, one selected, results highlighted + dimmed others.
- **Status:** [ ]

### U03.T04 — Map fallbacks & accessible alternative
- **Skills:** deckgl-track-map, ux-states-and-evidence
- **Depends on:** U03.T02
- **Files:** frontend/src/components/map/MapFallback.tsx, frontend/src/components/map/MapPointList.tsx
- **Do:**
  - WebGL failure and projection-unavailable views; keyboard-navigable list alternative of the same points; visually hidden summary for screen readers.
- **Done when:**
  - Stories for map-down and WebGL-failure; axe passes on the list alternative.
- **Status:** [ ]

## Exit criteria
- [ ] deck.gl appears only under `components/map/`; the map never fetches or computes similarity; fallbacks keep the experience usable without the map.
