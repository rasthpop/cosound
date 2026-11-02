// Map controls (ui.md §4.3, bottom-left): zoom ±, reset view, legend and list toggles, and the
// "Only tracks with audio" filter. Pure: every control emits an event.
import { List, Minus, Palette, Plus, RotateCcw } from "lucide-react";

import { ICON } from "@/theme/tokens/semantic";

import { Button } from "../ui/button";
import { Toggle } from "../ui/toggle";

export interface MapControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  /** Fit all points and clear the highlight (same as the `0` key). */
  onReset: () => void;
  legendOpen: boolean;
  onLegendToggle: (open: boolean) => void;
  listOpen: boolean;
  onListToggle: (open: boolean) => void;
  /** `has_audio` filter; omitted when the container doesn't offer it. */
  audioOnly?: boolean;
  onAudioOnlyChange?: (on: boolean) => void;
}

export function MapControls({
  onZoomIn,
  onZoomOut,
  onReset,
  legendOpen,
  onLegendToggle,
  listOpen,
  onListToggle,
  audioOnly,
  onAudioOnlyChange,
}: MapControlsProps) {
  return (
    <div role="toolbar" aria-label="Map controls" className="flex items-center gap-0.5 rounded-lg border border-hairline bg-surface-panel p-0.5 backdrop-blur-panel">
      <Button size="icon-sm" variant="ghost" aria-label="Zoom in" onClick={onZoomIn}>
        <Plus aria-hidden="true" {...ICON} />
      </Button>
      <Button size="icon-sm" variant="ghost" aria-label="Zoom out" onClick={onZoomOut}>
        <Minus aria-hidden="true" {...ICON} />
      </Button>
      <Button size="icon-sm" variant="ghost" aria-label="Reset view" onClick={onReset}>
        <RotateCcw aria-hidden="true" {...ICON} />
      </Button>
      <Toggle variant="plain" pressed={legendOpen} onPressedChange={onLegendToggle} aria-label="Genre legend">
        <Palette aria-hidden="true" {...ICON} />
      </Toggle>
      <Toggle variant="plain" pressed={listOpen} onPressedChange={onListToggle} aria-label="List of map tracks">
        <List aria-hidden="true" {...ICON} />
      </Toggle>
      {onAudioOnlyChange && (
        <Toggle variant="plain" pressed={audioOnly ?? false} onPressedChange={onAudioOnlyChange}>
          Only tracks with audio
        </Toggle>
      )}
    </div>
  );
}
