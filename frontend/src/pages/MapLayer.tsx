// The map container (ui.md §4.3): `useMusicMap` state → TrackMap and its chrome. It owns only map
// UI state (legend and list open, zoom requests, a WebGL failure). Which tracks are highlighted,
// selected or hovered, and where the camera should go, come from the Discover screen, so the list
// and the map share one selection.
//
// It returns the canvas and the controls separately because the layout puts them in different
// zones (the canvas behind everything, the controls under the results panel).
import { useState, type ReactNode } from "react";

import { GenreLegend } from "@/components/map/GenreLegend";
import { MapCaption } from "@/components/map/MapCaption";
import { MapControls } from "@/components/map/MapControls";
import { MapFallback } from "@/components/map/MapFallback";
import { MapPointList } from "@/components/map/MapPointList";
import { MapTooltip } from "@/components/map/MapTooltip";
import { TrackMap, type FitRequest } from "@/components/map/TrackMap";
import type { MusicMap } from "@/hooks";

import { withAudioOnly, withGenre } from "./selection";

export interface MapLayerProps {
  map: MusicMap;
  /** Results on this map (resultsOnMap). */
  highlightedTrackIds: ReadonlySet<string>;
  /** Results are shown: dim everything else. */
  dimUnhighlighted: boolean;
  hoveredTrackId: string | null;
  fitTo: FitRequest | null;
  /** A row of the list alternative was chosen. */
  onTrackSelect: (trackId: string) => void;
  /** A point on the canvas was clicked (focus later returns to the map). */
  onPointSelect: (trackId: string) => void;
  onTrackHover: (trackId: string | null) => void;
  /** Reset view (control or `0`): fit all points and clear the highlight, keeping the list. */
  onReset: () => void;
  /** The results panel is on screen: the legend starts collapsed so the panel keeps its height. */
  resultsShown?: boolean;
}

export const MAP_LABEL = "Map of tracks by audio similarity";

export function useMapLayer({
  map,
  highlightedTrackIds,
  dimUnhighlighted,
  hoveredTrackId,
  fitTo,
  onTrackSelect,
  onPointSelect,
  onTrackHover,
  onReset,
  resultsShown = false,
}: MapLayerProps): { canvas: ReactNode; controls: ReactNode } {
  // the user's own choice wins; until they make one, open on the idle map, closed beside results
  const [legendChoice, setLegendChoice] = useState<boolean | null>(null);
  const legendOpen = legendChoice ?? !resultsShown;
  const [listOpen, setListOpen] = useState(false);
  const [zoom, setZoom] = useState<{ delta: number; key: number } | null>(null);
  const [webglFailed, setWebglFailed] = useState(false);

  const zoomBy = (delta: number) => setZoom((z) => ({ delta, key: (z?.key ?? 0) + 1 }));
  const list = (
    <MapPointList
      points={map.points}
      highlightedTrackIds={highlightedTrackIds}
      selectedTrackIds={map.selectedTrackIds}
      onTrackSelect={onTrackSelect}
    />
  );

  // the map is down (no projection, or its requests fail): a calm message; search is unaffected
  if (map.availability === "unavailable" || map.availability === "error") {
    return { canvas: <MapFallback reason="unavailable" />, controls: null };
  }
  if (webglFailed) {
    return { canvas: <MapFallback reason="webgl">{list}</MapFallback>, controls: <MapCaption /> };
  }

  const canvas = (
    <TrackMap
      points={map.points}
      genres={map.meta?.genres ?? null}
      bounds={map.meta?.bounds ?? null}
      selectedTrackIds={map.selectedTrackIds}
      highlightedTrackIds={highlightedTrackIds}
      hoveredTrackId={hoveredTrackId}
      dimUnhighlighted={dimUnhighlighted}
      fitTo={fitTo}
      zoomBy={zoom}
      onTrackSelect={onPointSelect}
      onTrackHover={onTrackHover}
      onResetRequest={onReset}
      onWebGLError={() => setWebglFailed(true)}
      renderTooltip={(point) => <MapTooltip point={point} />}
      ariaLabel={MAP_LABEL}
    />
  );

  const controls = (
    <>
      {listOpen && list}
      {legendOpen && (
        <GenreLegend
          genres={map.meta?.genres}
          activeGenre={map.filters.genre ?? null}
          onGenreFilter={(genre) => map.setFilters(withGenre(map.filters, genre))}
        />
      )}
      <MapControls
        onZoomIn={() => zoomBy(1)}
        onZoomOut={() => zoomBy(-1)}
        onReset={onReset}
        legendOpen={legendOpen}
        onLegendToggle={setLegendChoice}
        listOpen={listOpen}
        onListToggle={setListOpen}
        audioOnly={map.filters.has_audio === true}
        onAudioOnlyChange={(on) => map.setFilters(withAudioOnly(map.filters, on))}
      />
      <MapCaption />
    </>
  );
  return { canvas, controls };
}
