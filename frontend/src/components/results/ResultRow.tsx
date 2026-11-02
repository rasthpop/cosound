// One ranked result (ui.md §4.2): rank · title · artists · genre/style badges · evidence note ·
// description and match reasons exactly as returned · play only with a playable URL · feedback
// actions revealed on hover or keyboard focus · "not on map" when there are no coordinates.
// Views never compute relevance: everything shown here comes from the API as is.
import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

import type { TrackResult } from "@/api/types";
import { ICON } from "@/theme/tokens/semantic";

import { MiniPlayer } from "../audio/MiniPlayer";
import { formatArtists } from "../format/text";
import { Badge } from "../ui/badge";
import { cn } from "../ui/cn";
import { EvidenceNote } from "./EvidenceNote";
import { MatchBand } from "./MatchBand";
import { NotOnMapMarker } from "./NotOnMapMarker";

export type ResultRowData = Pick<
  TrackResult,
  | "track_id"
  | "rank"
  | "title"
  | "artists"
  | "genres"
  | "styles"
  | "description"
  | "match_reasons"
  | "evidence_status"
  | "uncertainty_flags"
  | "retrieval_sources"
  | "spatial"
  | "source_url"
  | "match_strength"
>;

export interface ResultRowProps {
  result: ResultRowData;
  /** A playable URL for `preview_url`, resolved by the container; `null` = no play button. */
  playUrl: string | null;
  playing?: boolean;
  selected?: boolean;
  /** Its point is hovered on the map (cross-highlight). */
  hovered?: boolean;
  /** Feedback actions (FeedbackActions), shown on hover and keyboard focus. */
  actions?: ReactNode;
  onTrackSelect: (trackId: string) => void;
  onTrackHover?: (trackId: string | null) => void;
  /** `trackId` to play it, `null` to pause. */
  onPlay?: (trackId: string | null) => void;
}

export function ResultRow({ result, playUrl, playing = false, selected = false, hovered = false, actions, onTrackSelect, onTrackHover, onPlay }: ResultRowProps) {
  const artists = formatArtists(result.artists);
  const tags = [...result.genres, ...result.styles];
  const reasons = result.match_reasons.filter((r) => r.trim());
  return (
    <li
      aria-current={selected ? "true" : undefined}
      onMouseEnter={() => onTrackHover?.(result.track_id)}
      onMouseLeave={() => onTrackHover?.(null)}
      onFocus={() => onTrackHover?.(result.track_id)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) onTrackHover?.(null);
      }}
      className={cn(
        "group relative flex min-h-7 gap-1 rounded-md border border-transparent px-1 py-1 hover:bg-surface-raised",
        hovered && "bg-surface-raised",
        selected && "border-accent bg-surface-raised",
      )}
    >
      <span className="w-2 shrink-0 pt-0.5 text-right text-meta text-muted tabular-nums">{result.rank}</span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex flex-wrap items-baseline gap-x-1">
          <button
            type="button"
            onClick={() => onTrackSelect(result.track_id)}
            className="cursor-pointer truncate text-left text-body font-medium text-fg hover:underline"
          >
            {result.title}
          </button>
          <MatchBand band={result.match_strength} />
        </div>
        {artists && <p className="truncate text-meta text-muted">{artists}</p>}
        {tags.length > 0 && (
          <ul aria-label="Genres and styles" className="flex flex-wrap gap-0.5">
            {tags.map((tag) => (
              <li key={tag}>
                <Badge>{tag}</Badge>
              </li>
            ))}
          </ul>
        )}
        {result.description && <p className="line-clamp-2 text-meta text-fg">{result.description}</p>}
        {reasons.length > 0 && (
          <ul aria-label="Why it matched" className="flex flex-wrap gap-x-1 text-meta text-muted">
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
        <EvidenceNote
          evidence_status={result.evidence_status}
          uncertainty_flags={result.uncertainty_flags}
          retrieval_sources={result.retrieval_sources}
        />
        {result.spatial === null && <NotOnMapMarker />}
        {/* under the text, so the actions never narrow the title column; a feedback status (its <p>) keeps them visible */}
        {actions && (
          <div className="opacity-0 transition-opacity duration-(--token-motion-duration-fast) group-focus-within:opacity-100 group-hover:opacity-100 has-[p]:opacity-100">
            {actions}
          </div>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-0.5">
        {playUrl && onPlay && (
          <MiniPlayer src={playUrl} title={result.title} playing={playing} onPlayingChange={(on) => onPlay(on ? result.track_id : null)} />
        )}
        {result.source_url && (
          <a
            href={result.source_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open ${result.title} on FMA`}
            className="inline-flex size-4 items-center justify-center rounded-sm text-muted hover:bg-surface-raised hover:text-fg"
          >
            <ExternalLink aria-hidden="true" {...ICON} />
          </a>
        )}
      </div>
    </li>
  );
}
