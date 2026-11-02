// A result without map coordinates (no audio embedding, or the map is unavailable).
import { MapPinOff } from "lucide-react";

import { ICON } from "@/theme/tokens/semantic";

export function NotOnMapMarker() {
  return (
    <span className="inline-flex items-center gap-0.5 text-meta text-muted">
      <MapPinOff aria-hidden="true" {...ICON} />
      Not on map
    </span>
  );
}
