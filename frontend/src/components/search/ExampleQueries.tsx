// Example queries shown under an empty, focused search bar (ui.md §4.1). The copy is passed in by
// the container; this view only lists it.
import { ICON } from "@/theme/tokens/semantic";
import { Sparkles } from "lucide-react";

export interface ExampleQueriesProps {
  examples: readonly string[];
  onSelect: (query: string) => void;
}

export function ExampleQueries({ examples, onSelect }: ExampleQueriesProps) {
  if (examples.length === 0) return null;
  return (
    <div className="flex flex-col gap-0.5 p-1">
      <p id="example-queries-label" className="px-1 text-meta text-muted">
        Try
      </p>
      <ul aria-labelledby="example-queries-label" className="flex flex-col">
        {examples.map((example) => (
          <li key={example}>
            <button
              type="button"
              // keep focus in the input so the list does not close before the click lands
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onSelect(example)}
              className="flex w-full cursor-pointer items-center gap-1 rounded-md px-1 py-0.5 text-left text-body hover:bg-surface-raised"
            >
              <Sparkles aria-hidden="true" className="shrink-0 text-muted" {...ICON} />
              {example}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
