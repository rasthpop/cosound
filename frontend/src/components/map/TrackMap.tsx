// The track map (ui.md §4.3, deckgl-track-map). A pure renderer: it draws precomputed UMAP
// coordinates and emits events. It never fetches, never computes similarity and never decides
// which tracks are results; the container passes all of that in.
import { OrthographicView, type OrthographicViewState, type PickingInfo } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";
import DeckGL from "@deck.gl/react";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import type { MapPoint } from "@/api/types";
import { genreScale, type GenreCountLike } from "@/theme/scales/categorical";
import { toRgba } from "@/theme/scales/toRgba";
import { useTheme } from "@/theme/useTheme";

import { cameraTransition } from "./camera";
import { boundsOf, clampZoom, fitBounds, zoomRange, type Bounds, type Camera, type Viewport } from "./fitBounds";
import { setKey, triggerKeys } from "./keys";
import { accessors } from "./pointStyle";

export type TrackMapPoint = Pick<MapPoint, "track_id" | "x" | "y" | "genre" | "title" | "artist">;

export interface FitRequest {
  bounds: Bounds;
  /** Change it to fit again to the same bounds (e.g. "reset view" twice). */
  key: string | number;
}

export interface TrackMapProps {
  points: readonly TrackMapPoint[];
  /** `MapMeta.genres`: the colour domain, stable across filters and pages. */
  genres?: readonly GenreCountLike[] | null;
  /** `MapMeta.bounds`: the zoom range and the first view. */
  bounds?: Bounds | null;
  selectedTrackIds?: ReadonlySet<string>;
  /** Current search results. */
  highlightedTrackIds?: ReadonlySet<string>;
  hoveredTrackId?: string | null;
  /** Dim everything that is not highlighted (while results are shown). */
  dimUnhighlighted?: boolean;
  /** A camera request from the container: fit these bounds (results, or all points). */
  fitTo?: FitRequest | null;
  /** A zoom request (the ± controls): change zoom by `delta` levels, once per `key`. */
  zoomBy?: { delta: number; key: string | number } | null;
  onTrackSelect: (trackId: string) => void;
  onTrackHover?: (trackId: string | null) => void;
  /** The `0` key: the container fits all points and clears the highlight. */
  onResetRequest?: () => void;
  /** WebGL could not start or failed; the container shows the list fallback. */
  onWebGLError?: (error: Error) => void;
  /** Tooltip content for the hovered point (MapTooltip), placed at the pointer. */
  renderTooltip?: (point: TrackMapPoint) => ReactNode;
  ariaLabel: string;
}

const EMPTY: ReadonlySet<string> = new Set();
/** Pointer tolerance in px: the dots are 2–4 px, so a near miss still picks the nearest one. */
const PICKING_RADIUS = 6;
/** How far the pulse ring grows (×radius) before it fades out. */
const PULSE_GROWTH = 1.5;

/** Pulse phase 0 → 1, repeating every `periodMs`, while `active`; 0 otherwise. */
function usePulse(active: boolean, periodMs: number): number {
  const [phase, setPhase] = useState(0);
  useEffect(() => {
    if (!active || periodMs <= 0) return;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      setPhase(((now - start) % periodMs) / periodMs);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [active, periodMs]);
  return active ? phase : 0;
}
const VIEW = new OrthographicView({ id: "umap", flipY: false });

/** Additive "glow" on a dark canvas; normal blending on a light one, where additive washes out. */
const ADDITIVE = {
  blend: true,
  blendColorSrcFactor: "src-alpha",
  blendColorDstFactor: "one",
  blendAlphaSrcFactor: "one",
  blendAlphaDstFactor: "one-minus-src-alpha",
} as const;

function useViewport() {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<Viewport | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) setSize({ width, height });
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return { ref, size };
}

export function TrackMap({
  points,
  genres = null,
  bounds = null,
  selectedTrackIds = EMPTY,
  highlightedTrackIds = EMPTY,
  hoveredTrackId = null,
  dimUnhighlighted = false,
  fitTo = null,
  zoomBy = null,
  onTrackSelect,
  onTrackHover,
  onResetRequest,
  onWebGLError,
  renderTooltip,
  ariaLabel,
}: TrackMapProps) {
  const { tokens, motion, theme } = useTheme();
  const { ref, size } = useViewport();
  const [camera, setCamera] = useState<Camera | null>(null);
  const [tooltip, setTooltip] = useState<{ point: TrackMapPoint; x: number; y: number } | null>(null);

  // the projection's extent: from the meta, or from the points until the meta arrives
  const extent = useMemo(() => bounds ?? boundsOf(points), [bounds, points]);
  const range = useMemo(() => (extent && size ? zoomRange(extent, size) : null), [extent, size]);

  // camera requests from the container (fit results, reset view): applied once per key, during
  // render (React's "adjust state when a prop changes" pattern, no effect needed)
  const transition = useMemo(() => cameraTransition(motion), [motion]);
  const [fitted, setFitted] = useState<FitRequest["key"] | null>(null);
  if (fitTo && size && fitTo.key !== fitted) {
    setFitted(fitTo.key);
    const next = fitBounds(fitTo.bounds, size);
    setCamera(range ? clampZoom(next, range) : next);
  }
  // until the user or the container moves the camera, show everything
  const view = camera ?? (extent && size ? fitBounds(extent, size) : null);
  const [zoomed, setZoomed] = useState<string | number | null>(null);
  if (zoomBy && view && zoomBy.key !== zoomed) {
    setZoomed(zoomBy.key);
    const next = { target: view.target, zoom: view.zoom + zoomBy.delta };
    setCamera(range ? clampZoom(next, range) : next);
  }

  const scale = useMemo(() => genreScale(genres ?? [], tokens), [genres, tokens]);
  const pulse = usePulse(motion.pulse && selectedTrackIds.size > 0, motion.duration.pulse);
  const genreKey = useMemo(() => setKey((genres ?? []).map((g) => `${g.genre}`)), [genres]);
  const triggers = useMemo(
    () =>
      triggerKeys({
        selected: selectedTrackIds,
        highlighted: highlightedTrackIds,
        hovered: hoveredTrackId,
        dimUnhighlighted,
        themeKey: `${theme}|${genreKey}`,
      }),
    [selectedTrackIds, highlightedTrackIds, hoveredTrackId, dimUnhighlighted, theme, genreKey],
  );

  // The point layer changes only with data, state or theme; the pulse layer changes every frame
  // while a selection pulses, so it is memoized separately and the point layer stays the same
  // object between frames.
  const tracksLayer = useMemo(() => {
    const style = accessors({
      selected: selectedTrackIds,
      highlighted: highlightedTrackIds,
      hovered: hoveredTrackId,
      dimUnhighlighted,
      scale,
      tokens,
      motion,
    });
    const fade = motion.duration.base;
    return new ScatterplotLayer<TrackMapPoint>({
      id: "tracks",
      data: points,
      getPosition: (d) => [d.x, d.y],
      ...style,
      radiusUnits: "pixels",
      lineWidthUnits: "pixels",
      stroked: true,
      filled: true,
      pickable: true,
      parameters: theme === "dark" ? ADDITIVE : {},
      updateTriggers: triggers,
      // points fade in as pages arrive (instant under reduced motion)
      transitions: { getFillColor: { duration: fade, enter: (c: number[]) => [c[0] ?? 0, c[1] ?? 0, c[2] ?? 0, 0] } },
    });
  }, [points, selectedTrackIds, highlightedTrackIds, hoveredTrackId, dimUnhighlighted, scale, tokens, motion, theme, triggers]);

  const selectedPoints = useMemo(
    () => (selectedTrackIds.size > 0 ? points.filter((p) => selectedTrackIds.has(p.track_id)) : []),
    [points, selectedTrackIds],
  );
  // the slow selection pulse: an expanding, fading accent ring (never under reduced motion)
  const pulseLayer = useMemo(
    () =>
      motion.pulse && selectedPoints.length > 0
        ? new ScatterplotLayer<TrackMapPoint>({
            id: "selection-pulse",
            data: selectedPoints,
            getPosition: (d) => [d.x, d.y],
            getRadius: tokens.size.point.selected,
            radiusUnits: "pixels",
            radiusScale: 1 + PULSE_GROWTH * pulse,
            stroked: true,
            filled: false,
            getLineColor: toRgba(tokens.color.map.point.selected),
            getLineWidth: tokens.size.ring.selected,
            lineWidthUnits: "pixels",
            opacity: 1 - pulse,
            pickable: false,
          })
        : null,
    [motion.pulse, selectedPoints, tokens, pulse],
  );
  const layers = useMemo(() => (pulseLayer ? [tracksLayer, pulseLayer] : [tracksLayer]), [tracksLayer, pulseLayer]);

  const onClick = useCallback(
    (info: PickingInfo<TrackMapPoint>) => {
      if (info.object) onTrackSelect(info.object.track_id);
    },
    [onTrackSelect],
  );
  const onHover = useCallback(
    (info: PickingInfo<TrackMapPoint>) => {
      const point = info.object ?? null;
      setTooltip(point ? { point, x: info.x, y: info.y } : null);
      onTrackHover?.(point ? point.track_id : null);
    },
    [onTrackHover],
  );

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "0" && onResetRequest) {
      e.preventDefault();
      onResetRequest();
    }
  };

  const viewState: OrthographicViewState | undefined = view
    ? { target: view.target, zoom: view.zoom, ...(range ?? {}), ...transition }
    : undefined;
  const results = points.filter((p) => highlightedTrackIds.has(p.track_id)).length;

  return (
    <div
      ref={ref}
      role="region"
      aria-label={ariaLabel}
      aria-describedby="track-map-summary"
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="relative size-full outline-none"
    >
      <p id="track-map-summary" className="sr-only">
        Map of {points.length} tracks
        {results > 0 ? `; ${results} results highlighted` : ""}. Use the list view to browse them by keyboard.
      </p>
      {viewState && (
        <DeckGL
          views={VIEW}
          viewState={viewState}
          onViewStateChange={({ viewState: next }) => {
            const v = next as OrthographicViewState;
            const target = (v.target ?? [0, 0, 0]) as [number, number, number];
            const zoom = typeof v.zoom === "number" ? v.zoom : 0;
            setCamera(range ? clampZoom({ target, zoom }, range) : { target, zoom });
          }}
          controller={{ inertia: true, scrollZoom: true, doubleClickZoom: true, dragPan: true, touchZoom: true, keyboard: true }}
          layers={layers}
          pickingRadius={PICKING_RADIUS}
          onClick={onClick}
          onHover={onHover}
          onError={(error) => onWebGLError?.(error)}
          getCursor={({ isHovering, isDragging }) => (isDragging ? "grabbing" : isHovering ? "pointer" : "grab")}
        />
      )}
      {tooltip && renderTooltip && (
        <div className="pointer-events-none absolute z-10" style={{ left: tooltip.x, top: tooltip.y }}>
          {renderTooltip(tooltip.point)}
        </div>
      )}
    </div>
  );
}
