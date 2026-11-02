// "Wrong instrument…" (WRONG_INSTRUMENT): pick which requested instrument the track gets wrong.
// Options come from the interpreted query; with none, the picker is not shown.
import { useId } from "react";

import { Button } from "../ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";

export interface InstrumentPickerProps {
  /** `interpreted_query.instrument_preferences[].value`. */
  instruments: readonly string[];
  title: string;
  disabled?: boolean;
  onPick: (instrument: string) => void;
}

export function InstrumentPicker({ instruments, title, disabled = false, onPick }: InstrumentPickerProps) {
  const headingId = useId();
  if (instruments.length === 0) return null;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button size="sm" variant="quiet" disabled={disabled} aria-label={`Wrong instrument in ${title}…`}>
          Wrong instrument…
        </Button>
      </PopoverTrigger>
      <PopoverContent aria-labelledby={headingId} align="end" className="w-24">
        <p id={headingId} className="px-0.5 text-meta text-muted">
          Which instrument is wrong?
        </p>
        {instruments.map((instrument) => (
          <Button key={instrument} size="sm" variant="ghost" className="justify-start" onClick={() => onPick(instrument)}>
            {instrument}
          </Button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
