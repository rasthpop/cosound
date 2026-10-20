---
name: deckgl-track-map
description: Building the deck.gl track-map view — a pure renderer in frontend/src/components/map/ that takes precomputed UMAP points and emits selection/hover events, using OrthographicView (non-geographic coordinates), ScatterplotLayer picking, updateTriggers, fit-to-bounds, highlighting search results, accessibility fallbacks, and performance limits. Load for any work on the map view or its container wiring with useMusicMap.
---

# deck.gl Track Map

Spec: `base.md` §11.4, §13.4, §14.3 (`useMusicMap`), §14.4. References: https://deck.gl/docs/api-reference/layers/scatterplot-layer, https://deck.gl/next/docs/developer-guide/interactivity, https://deck.gl/examples.

## 1. Contract

```tsx
// components/map/TrackMap.tsx — the ONLY file family importing @deck.gl/*
export interface TrackMapProps {
  points: ReadonlyArray<Pick<MapPoint, "track_id" | "x" | "y" | "genre" | "title" | "artist">>;
  selectedTrackIds?: ReadonlySet<string>;
  highlightedTrackIds?: ReadonlySet<string>;   // e.g. current search results
  dimUnhighlighted?: boolean;
  onTrackSelect?: (trackId: string) => void;
  onTrackHover?: (trackId: string | null) => void;
  colorFor?: (p: TrackMapProps["points"][number]) => RGBA;  // from theme scales; default provided
  ariaLabel: string;
}
```

The map **receives** coordinates. It never fetches, never computes UMAP/similarity, never decides which tracks are results. `useMusicMap` (functional track) stays deck.gl-free; the container passes `points`, `selectedTrackIds`, and wires `onTrackSelect` to `useTrackDetails` / search actions.

## 2. Non-geographic view

UMAP coordinates are not lat/lng. Use `OrthographicView`, not `MapView`, and no basemap:

```tsx
import DeckGL from "@deck.gl/react";
import { OrthographicView } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";

const view = new OrthographicView({ id: "umap", flipY: false });

const layer = new ScatterplotLayer<Point>({
  id: "tracks",
  data: points,
  getPosition: (d) => [d.x, d.y],
  getFillColor: (d) => colorFor(d),
  getRadius: (d) => (selected.has(d.track_id) ? r.selected : r.default),
  radiusUnits: "pixels",
  stroked: true,
  getLineColor: (d) => (selected.has(d.track_id) ? lineSelected : lineNone),
  lineWidthUnits: "pixels",
  pickable: true,
  autoHighlight: true,
  onClick: (info) => info.object && onTrackSelect?.(info.object.track_id),
  onHover: (info) => onTrackHover?.(info.object?.track_id ?? null),
  updateTriggers: { getFillColor: [colorKey, highlightKey], getRadius: [selectedKey], getLineColor: [selectedKey] },
});
```

- **`updateTriggers`** must list whatever the accessors close over (selection, highlight, theme) — otherwise deck.gl won't recompute attributes. Derive stable keys (e.g. a joined/sorted id string or a version counter), not new Set identities.
- **Fit to bounds:** compute the initial `viewState` (`target` = bbox center, `zoom = log2(min(width/bw, height/bh) · padding)`) in a pure helper `fitBounds.ts` (unit-tested). Recompute only when `projection_version` changes, not on every data page.
- Keep `viewState` controlled in the map component (or container if the UI plan needs camera sync); `controller` options (zoom limits, inertia) come from the UI plan.
- Stable layer `id`s; memoize `layers` with `useMemo` on data/trigger keys.
- Picking returns the original datum (`info.object`) — use `track_id` from it; never index by position.

## 3. Search results on the map

Container intersects `searchResults.track_id` with `points` → `highlightedTrackIds`. Tracks in results without coordinates (no audio / not projected) are listed by the container as "not on map" — the map doesn't invent positions for them.

## 4. Honest labeling

The map is for exploration. Copy around it (from the UI plan) must not claim "distance = similarity". Neighbors shown in details come from `GET /api/tracks/{id}/neighbors` (original space), not from 2D distance.

## 5. Accessibility & fallbacks

- Canvas is invisible to screen readers: provide `ariaLabel`, a visually-hidden summary ("Map of N tracks; M results highlighted"), and keyboard access to the same tracks through a list view (the plate or a map-list toggle).
- Detect WebGL failure (`onError`) → render a fallback message + list; search must keep working (base §16 "If the map projection is unavailable, search must still work").
- Respect `prefers-reduced-motion` for camera transitions.

## 6. Performance

ScatterplotLayer handles 10⁵–10⁶ points; the API paginates (base §13.4). Append pages to `data` only when `projection_version` is unchanged; on version change reset everything. Avoid per-frame React state for hover (debounce/throttle the hover callback or keep hover inside deck.gl `autoHighlight`).

## 7. Tests

- Pure helpers (`fitBounds`, color/radius pickers, key derivation) with vitest.
- Component test with deck.gl mocked (or `@deck.gl/test-utils` if adopted) asserting layer props and that `onClick` with an object emits `onTrackSelect(track_id)`.
- Visual check in the workbench against fixture points (`mocks/fixtures/map_points.json`) — empty, 20 points, 10k synthetic points, one selected, results highlighted, WebGL-failure fallback.
