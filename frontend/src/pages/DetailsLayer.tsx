// The details drawer container (ui.md §4.4): `useTrackDetails` + `useMediaUrl` → TrackDetailsDrawer.
// The catalog facts come from the details endpoint; description, match reasons and score bands
// come from the matching row of the current plate (joined by `track_id`) and are absent for a
// track opened from the map. Neighbors come from the API, never from map distance.
import type { ReactNode } from "react";

import type { TrackResult } from "@/api/types";
import { EvidenceNote } from "@/components/results/EvidenceNote";
import { NeighborList } from "@/components/track/NeighborList";
import { RelatedTracks } from "@/components/track/RelatedTracks";
import { ScoreBands } from "@/components/track/ScoreBands";
import { TrackDetailsDrawer, type DetailsStatus } from "@/components/track/TrackDetailsDrawer";
import { useMediaUrl, useTrackDetails, type RequestStatus } from "@/hooks";

export interface DetailsLayerProps {
  /** The selected track; `null` = closed. */
  trackId: string | null;
  /** The map's projection version: a new projection drops cached details. */
  projectionVersion: string | null;
  /** The track's row in the current plate, if it is in it. */
  result: TrackResult | null;
  /** Feedback actions, only for tracks in the current plate (the API refers feedback to it). */
  actions?: ReactNode;
  variant: "desktop" | "mobile";
  onClose: () => void;
  /** After closing: move focus back to where the selection came from. */
  onCloseAutoFocus: (event: Event) => void;
  /** A neighbor or related track: the same action as selecting it on the map. */
  onTrackSelect: (trackId: string) => void;
}

function drawerStatus(status: RequestStatus): DetailsStatus {
  if (status === "error") return "error";
  return status === "success" ? "ready" : "loading";
}

export function DetailsLayer({ trackId, projectionVersion, result, actions, variant, onClose, onCloseAutoFocus, onTrackSelect }: DetailsLayerProps) {
  const details = useTrackDetails(trackId, { withNeighbors: true, ...(projectionVersion ? { projectionVersion } : {}) });
  const playUrl = useMediaUrl(details.detail?.preview_url ?? null);
  const detail = details.detail;

  const related = detail ? (
    <>
      {/* neighbors that failed to load are left out rather than shown as an endless placeholder */}
      {!details.neighborsError && <NeighborList neighbors={details.neighbors} onTrackSelect={onTrackSelect} />}
      <RelatedTracks related={detail.related_tracks} onTrackSelect={onTrackSelect} />
    </>
  ) : null;

  return (
    <TrackDetailsDrawer
      open={trackId !== null}
      onClose={onClose}
      onCloseAutoFocus={onCloseAutoFocus}
      variant={variant}
      status={drawerStatus(details.status)}
      detail={detail}
      error={details.error}
      playUrl={playUrl}
      description={result?.description ?? null}
      matchReasons={result?.match_reasons ?? []}
      actions={actions}
      // what the match rests on (the row's flags), or for a track opened from the map, whether it
      // has audio analysis at all
      evidence={
        result ? (
          <>
            <EvidenceNote evidence_status={result.evidence_status} uncertainty_flags={result.uncertainty_flags} retrieval_sources={result.retrieval_sources} />
            <ScoreBands bands={result.score_bands} />
          </>
        ) : detail ? (
          <EvidenceNote evidence_status={detail.evidence_status} uncertainty_flags={[]} retrieval_sources={[]} />
        ) : null
      }
      related={related}
    />
  );
}
