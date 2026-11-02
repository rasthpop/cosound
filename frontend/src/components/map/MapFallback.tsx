// When there is no map to draw: the projection is unavailable (calm message, search unaffected),
// or WebGL failed (the same tracks as a list instead).
import { MapPinOff } from "lucide-react";
import type { ReactNode } from "react";

import { ICON } from "@/theme/tokens/semantic";

export interface MapFallbackProps {
  reason: "unavailable" | "webgl";
  /** The list alternative (MapPointList), shown with the WebGL fallback. */
  children?: ReactNode;
}

const COPY = {
  unavailable: "Map is unavailable — search still works.",
  webgl: "Your browser couldn't draw the map, so its tracks are listed instead. Search still works.",
} as const;

export function MapFallback({ reason, children }: MapFallbackProps) {
  return (
    <div className="flex size-full flex-col items-center justify-center gap-2 bg-surface-canvas p-3 text-fg">
      <p role="status" className="flex items-center gap-1 text-body text-muted">
        <MapPinOff aria-hidden="true" {...ICON} />
        {COPY[reason]}
      </p>
      {children}
    </div>
  );
}
