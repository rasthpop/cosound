// Degraded-mode pill (ui.md §4.5, ux-states-and-evidence §1). Renders nothing unless something is
// degraded. Each line has an icon and text; colour is never the only signal.
import { AudioLines, MapPinOff, WifiOff } from "lucide-react";

import type { Capabilities } from "@/api/types";
import { ICON } from "@/theme/tokens/semantic";

import { Button } from "../ui/button";

export interface StatusPillProps {
  /** From the latest search (or health) response; `null` before any arrived. */
  capabilities: Pick<Capabilities, "semantic" | "map"> | null;
  /** The last request failed without reaching the server. */
  offline?: boolean;
  onRetry?: () => void;
}

export function StatusPill({ capabilities, offline = false, onRetry }: StatusPillProps) {
  const semanticDown = capabilities?.semantic === "unavailable";
  const mapDown = capabilities?.map === "unavailable";
  if (!semanticDown && !mapDown && !offline) return null;
  return (
    <div
      role="status"
      className="flex flex-col gap-0.5 rounded-lg border border-hairline bg-surface-panel px-1.5 py-1 text-meta backdrop-blur-panel"
    >
      {offline && (
        <p className="flex items-center gap-1">
          <WifiOff aria-hidden="true" className="text-state-error" {...ICON} />
          <span>Offline</span>
          {onRetry && (
            <Button size="sm" variant="ghost" onClick={onRetry}>
              Retry
            </Button>
          )}
        </p>
      )}
      {semanticDown && (
        <p className="flex items-center gap-1">
          <AudioLines aria-hidden="true" className="text-state-degraded" {...ICON} />
          <span>Sound-based matching is off — catalog data only</span>
        </p>
      )}
      {mapDown && (
        <p className="flex items-center gap-1">
          <MapPinOff aria-hidden="true" className="text-state-degraded" {...ICON} />
          <span>Map unavailable</span>
        </p>
      )}
    </div>
  );
}
