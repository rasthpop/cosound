// Map ⇄ plate bookkeeping for the Discover screen (ui.md §4.3, deckgl-track-map §3). Pure: which
// results the map can show, and the camera requests that go with them. No similarity, no ranking.
import type { MapFilters, Spatial } from "@/api/types";
import { boundsOf, type Bounds } from "@/components/map/fitBounds";

type WithSpatial = { track_id: string; spatial: Spatial | null };

/** Results drawn on the current map: they have coordinates from *this* projection version. The
 * rest show as "not on map" in the list; the map never invents positions for them. The camera fits
 * where the points are drawn (the loaded point), falling back to the result's own coordinates. */
export function resultsOnMap(
  results: readonly WithSpatial[],
  points: ReadonlyArray<{ track_id: string; x: number; y: number }>,
  projectionVersion: string | null,
): { ids: ReadonlySet<string>; bounds: Bounds | null } {
  if (projectionVersion === null) return { ids: new Set(), bounds: null };
  const placed = results.filter((r) => r.spatial !== null && r.spatial.projection_version === projectionVersion);
  const byId = new Map(points.map((p) => [p.track_id, p]));
  return {
    ids: new Set(placed.map((r) => r.track_id)),
    bounds: boundsOf(placed.map((r) => byId.get(r.track_id) ?? (r.spatial as Spatial))),
  };
}

/** Bounds of one point, for easing the camera to a selected track (fitBounds widens a single point). */
export function pointBounds(point: { x: number; y: number }): Bounds {
  return { min_x: point.x, max_x: point.x, min_y: point.y, max_y: point.y };
}

/** Where a track sits on the current map: the loaded point, else the result's own coordinates
 * when they are from the same projection. `null` when it is not on this map. */
export function locate(
  trackId: string,
  points: ReadonlyArray<{ track_id: string; x: number; y: number }>,
  results: readonly WithSpatial[],
  projectionVersion: string | null,
): { x: number; y: number } | null {
  const point = points.find((p) => p.track_id === trackId);
  if (point) return point;
  const spatial = results.find((r) => r.track_id === trackId)?.spatial;
  return spatial && spatial.projection_version === projectionVersion ? spatial : null;
}

/** The legend's genre filter applied to the current filters (other filters are kept). */
export function withGenre(filters: MapFilters, genre: string | null): MapFilters {
  const next: MapFilters = { ...filters };
  if (genre === null) delete next.genre;
  else next.genre = genre;
  return next;
}
