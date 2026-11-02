// Neighbors of the open track, from GET /api/tracks/{id}/neighbors (original embedding space, not
// map distance). The heading says how they were found; a catalog fallback shows its reason.
import type { NeighborsResponse } from "@/api/types";

import { formatArtists } from "../format/text";
import { neighborMetricLabel, neighborReasonLabel } from "../format/labels";
import { Skeleton } from "../ui/skeleton";

export interface NeighborListProps {
  /** `null` while loading. */
  neighbors: Pick<NeighborsResponse, "metric" | "neighbors" | "reason"> | null;
  onTrackSelect: (trackId: string) => void;
}

export function NeighborList({ neighbors, onTrackSelect }: NeighborListProps) {
  if (neighbors === null) {
    return (
      <section aria-label="Nearby tracks" aria-busy="true" className="flex flex-col gap-0.5">
        <Skeleton className="h-2 w-20" />
        <Skeleton className="h-2 w-30" />
      </section>
    );
  }
  const heading = neighborMetricLabel(neighbors.metric);
  const reason = neighborReasonLabel(neighbors.reason);
  return (
    <section aria-label={heading} className="flex flex-col gap-0.5">
      <h3 className="text-body font-medium">{heading}</h3>
      {reason && <p className="text-meta text-muted">{reason}</p>}
      {neighbors.neighbors.length === 0 ? (
        <p className="text-meta text-muted">No nearby tracks found.</p>
      ) : (
        <ul className="flex flex-col">
          {neighbors.neighbors.map((n) => (
            <li key={n.track_id}>
              <button
                type="button"
                onClick={() => onTrackSelect(n.track_id)}
                className="flex w-full cursor-pointer flex-col rounded-md px-1 py-0.5 text-left hover:bg-surface-raised"
              >
                <span className="text-body">{n.title}</span>
                {formatArtists(n.artists) && <span className="text-meta text-muted">{formatArtists(n.artists)}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
