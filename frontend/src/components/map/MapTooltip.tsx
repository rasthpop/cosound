// What the map says about a point (ui.md §4.3): title · artist · genre, from `MapPoint` fields
// only. Absent fields are left out. On touch, the same content is a compact card in the sheet.
import type { MapPoint } from "@/api/types";

import { cn } from "../ui/cn";

export interface MapTooltipProps {
  point: Pick<MapPoint, "title" | "artist" | "genre">;
  /** `floating` follows the pointer; `card` sits in the mobile sheet. */
  variant?: "floating" | "card";
}

export function MapTooltip({ point, variant = "floating" }: MapTooltipProps) {
  const meta = [point.artist, point.genre].filter((v): v is string => Boolean(v));
  return (
    <div
      role={variant === "card" ? "group" : "tooltip"}
      aria-label={variant === "card" ? point.title : undefined}
      className={cn(
        "flex max-w-40 flex-col rounded-sm border border-hairline bg-surface-raised px-1 py-0.5 text-fg backdrop-blur-panel",
        variant === "floating" && "translate-x-1 -translate-y-full",
        variant === "card" && "w-full max-w-none rounded-md p-1",
      )}
    >
      <span className="truncate text-body font-medium">{point.title}</span>
      {meta.length > 0 && <span className="truncate text-meta text-muted">{meta.join(" · ")}</span>}
    </div>
  );
}
