// Camera fitting for the non-geographic UMAP view (OrthographicView: zoom z means 2^z screen px
// per coordinate unit). Pure functions, unit-tested; no deck.gl import.

export interface Bounds {
  min_x: number;
  max_x: number;
  min_y: number;
  max_y: number;
}

export interface Viewport {
  width: number;
  height: number;
}

export interface Camera {
  target: [number, number, number];
  zoom: number;
}

export interface ZoomRange {
  minZoom: number;
  maxZoom: number;
}

/** Padding around fitted points in CSS px (ui.md §4.3: results fit with 80 px). */
export const FIT_PADDING = 80;
/** How far out from "everything fits" the user may zoom, and how far in. */
const ZOOM_OUT_SLACK = 1;
const ZOOM_IN_RANGE = 10;
/** Zoom for a single point: as if it were alone in a span of this many coordinate units. */
const SINGLE_POINT_SPAN = 0.5;

/** The bounding box of points; `null` when there are none or a coordinate is not finite. */
export function boundsOf(points: ReadonlyArray<{ x: number; y: number }>): Bounds | null {
  let b: Bounds | null = null;
  for (const { x, y } of points) {
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    b = b
      ? { min_x: Math.min(b.min_x, x), max_x: Math.max(b.max_x, x), min_y: Math.min(b.min_y, y), max_y: Math.max(b.max_y, y) }
      : { min_x: x, max_x: x, min_y: y, max_y: y };
  }
  return b;
}

/** Camera that shows `bounds` inside the viewport minus `padding` on every side. */
export function fitBounds(bounds: Bounds, viewport: Viewport, padding = FIT_PADDING): Camera {
  const width = Math.max(viewport.width - 2 * padding, 1);
  const height = Math.max(viewport.height - 2 * padding, 1);
  const spanX = Math.max(bounds.max_x - bounds.min_x, 0);
  const spanY = Math.max(bounds.max_y - bounds.min_y, 0);
  const span = (s: number) => (s > 0 ? s : SINGLE_POINT_SPAN);
  const scale = Math.min(width / span(spanX), height / span(spanY));
  return {
    target: [(bounds.min_x + bounds.max_x) / 2, (bounds.min_y + bounds.max_y) / 2, 0],
    zoom: Math.log2(scale),
  };
}

/** Allowed zoom: a little further out than the whole projection, and a fixed range in. */
export function zoomRange(projection: Bounds, viewport: Viewport): ZoomRange {
  const all = fitBounds(projection, viewport, 0).zoom;
  return { minZoom: all - ZOOM_OUT_SLACK, maxZoom: all + ZOOM_IN_RANGE };
}

export function clampZoom(camera: Camera, range: ZoomRange): Camera {
  return { ...camera, zoom: Math.min(range.maxZoom, Math.max(range.minZoom, camera.zoom)) };
}
