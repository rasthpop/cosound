// The map's tracks as a keyboard-navigable list: the accessible alternative to the canvas and the
// WebGL fallback. Same points, same order, shown a page at a time.
import { useState } from "react";

import type { MapPoint } from "@/api/types";

import { Button } from "../ui/button";
import { cn } from "../ui/cn";
import { ScrollArea } from "../ui/scroll-area";

export interface MapPointListProps {
  points: ReadonlyArray<Pick<MapPoint, "track_id" | "title" | "artist" | "genre">>;
  highlightedTrackIds?: ReadonlySet<string>;
  selectedTrackIds?: ReadonlySet<string>;
  onTrackSelect: (trackId: string) => void;
  /** Rows shown before "Show more". */
  pageSize?: number;
}

const EMPTY: ReadonlySet<string> = new Set();

export function MapPointList({ points, highlightedTrackIds = EMPTY, selectedTrackIds = EMPTY, onTrackSelect, pageSize = 100 }: MapPointListProps) {
  const [shown, setShown] = useState(pageSize);
  const visible = points.slice(0, shown);
  return (
    <section aria-label="Tracks on the map" className="flex max-h-full w-47.5 flex-col rounded-lg border border-hairline bg-surface-panel text-fg backdrop-blur-panel">
      <h2 className="px-2 pt-1.5 pb-1 text-body font-medium">
        {points.length} {points.length === 1 ? "track" : "tracks"} on the map
      </h2>
      <ScrollArea className="min-h-0 flex-1">
        <ul className="flex flex-col px-1 pb-1">
          {visible.map((p) => {
            const result = highlightedTrackIds.has(p.track_id);
            const meta = [p.artist, p.genre].filter((v): v is string => Boolean(v)).join(" · ");
            return (
              <li key={p.track_id}>
                <button
                  type="button"
                  aria-current={selectedTrackIds.has(p.track_id) ? "true" : undefined}
                  onClick={() => onTrackSelect(p.track_id)}
                  className={cn(
                    "flex w-full cursor-pointer flex-col rounded-md border border-transparent px-1 py-0.5 text-left hover:bg-surface-raised",
                    selectedTrackIds.has(p.track_id) && "border-accent",
                  )}
                >
                  <span className="text-body">
                    {p.title}
                    {result && <span className="ml-1 text-meta text-muted">· in results</span>}
                  </span>
                  {meta && <span className="text-meta text-muted">{meta}</span>}
                </button>
              </li>
            );
          })}
        </ul>
        {shown < points.length && (
          <div className="px-2 pb-1.5">
            <Button size="sm" onClick={() => setShown((n) => n + pageSize)}>
              Show {Math.min(pageSize, points.length - shown)} more
            </Button>
          </div>
        )}
      </ScrollArea>
    </section>
  );
}
