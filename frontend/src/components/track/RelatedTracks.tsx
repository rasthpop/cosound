// Catalog relationships of the open track (same artist, same release, …), grouped by type.
import type { RelatedTrack, RelationshipType } from "@/api/types";

import { formatArtists } from "../format/text";
import { relationshipLabel } from "../format/labels";

export interface RelatedTracksProps {
  related: readonly RelatedTrack[];
  onTrackSelect: (trackId: string) => void;
}

export function RelatedTracks({ related, onTrackSelect }: RelatedTracksProps) {
  if (related.length === 0) return null;
  const groups = new Map<RelationshipType, RelatedTrack[]>();
  for (const r of related) groups.set(r.relationship_type, [...(groups.get(r.relationship_type) ?? []), r]);
  return (
    <section aria-label="Related in the catalog" className="flex flex-col gap-1">
      <h3 className="text-body font-medium">Related in the catalog</h3>
      {[...groups].map(([type, tracks]) => (
        <div key={type} className="flex flex-col gap-0.5">
          <h4 className="text-meta text-muted">{relationshipLabel(type)}</h4>
          <ul className="flex flex-col">
            {tracks.map((t) => (
              <li key={`${type}:${t.track_id}`}>
                <button
                  type="button"
                  onClick={() => onTrackSelect(t.track_id)}
                  className="flex w-full cursor-pointer flex-col rounded-md px-1 py-0.5 text-left hover:bg-surface-raised"
                >
                  <span className="text-body">{t.title}</span>
                  {formatArtists(t.artists) && <span className="text-meta text-muted">{formatArtists(t.artists)}</span>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
