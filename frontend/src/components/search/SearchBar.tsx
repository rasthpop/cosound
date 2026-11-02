// The search input (ui.md §4.1). Controlled: the container owns the text, so it survives errors
// and offline retries. Enter or the arrow submits; Esc blurs. While a search runs a thin
// indeterminate line runs along the bottom edge. With `canRefine`, a Refine toggle (off by
// default, D2) sends the text as feedback on the current results instead of a new search.
import { ArrowRight } from "lucide-react";
import { useId, useState, type Ref } from "react";

import { ICON } from "@/theme/tokens/semantic";

import { Button } from "../ui/button";
import { cn } from "../ui/cn";
import { Toggle } from "../ui/toggle";
import { ExampleQueries } from "./ExampleQueries";

export const SEARCH_PLACEHOLDER = "Describe a sound… e.g. something chill with a flute";

export interface SearchBarProps {
  value: string;
  onValueChange: (text: string) => void;
  onQuerySubmit: (text: string) => void;
  /** A search or refinement is running. */
  loading?: boolean;
  /** The results on screen are from an earlier query (shown while `loading`). */
  stale?: boolean;
  /** Shown when the input is empty and focused. */
  examples?: readonly string[];
  /** Results are on screen, so the text can refine them (D2). */
  canRefine?: boolean;
  onRefineSubmit?: (text: string) => void;
  /** The container focuses the input for the `/` shortcut. */
  inputRef?: Ref<HTMLInputElement>;
}

export function SearchBar({
  value,
  onValueChange,
  onQuerySubmit,
  loading = false,
  stale = false,
  examples = [],
  canRefine = false,
  onRefineSubmit,
  inputRef,
}: SearchBarProps) {
  const [focused, setFocused] = useState(false);
  const [refine, setRefine] = useState(false);
  const inputId = useId();
  const refining = canRefine && refine && onRefineSubmit !== undefined;

  const submit = (text = value) => {
    const query = text.trim();
    if (!query) return;
    if (refining) onRefineSubmit(query);
    else onQuerySubmit(query);
  };

  const showExamples = focused && value.trim() === "" && examples.length > 0;

  return (
    <div className="relative w-full max-w-80">
      <form
        role="search"
        aria-busy={loading}
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="relative flex items-center gap-1 overflow-hidden rounded-lg border border-hairline bg-surface-panel py-0.5 pr-0.5 pl-1.5 backdrop-blur-panel"
      >
        <label htmlFor={inputId} className="sr-only">
          {refining ? "Refine the current results" : "Search by describing a sound"}
        </label>
        <input
          id={inputId}
          ref={inputRef}
          value={value}
          placeholder={SEARCH_PLACEHOLDER}
          autoComplete="off"
          onChange={(e) => onValueChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(e) => {
            if (e.key === "Escape") e.currentTarget.blur();
          }}
          className="h-5 min-w-0 flex-1 bg-transparent text-body text-fg outline-none placeholder:text-muted"
        />
        {stale && loading && <span className="text-meta text-muted">Updating…</span>}
        {canRefine && onRefineSubmit && (
          <Toggle pressed={refine} onPressedChange={setRefine} aria-label="Refine the current results">
            Refine
          </Toggle>
        )}
        <Button type="submit" variant="primary" size="icon" aria-label={refining ? "Refine" : "Search"} disabled={!value.trim()}>
          <ArrowRight aria-hidden="true" {...ICON} />
        </Button>
        {loading && (
          <span role="progressbar" aria-label="Searching" className="absolute inset-x-0 bottom-0 h-px overflow-hidden">
            <span className="block h-full w-2/5 animate-progress bg-accent" />
          </span>
        )}
      </form>
      {showExamples && (
        <div className={cn("absolute inset-x-0 top-full z-30 mt-0.5 rounded-lg border border-hairline bg-surface-panel backdrop-blur-panel")}>
          <ExampleQueries
            examples={examples}
            onSelect={(example) => {
              onValueChange(example);
              submit(example);
            }}
          />
        </div>
      )}
    </div>
  );
}
