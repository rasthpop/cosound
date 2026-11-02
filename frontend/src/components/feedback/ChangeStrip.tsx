// "What changed" after feedback (ui.md §4.2): a dismissible list, with the original query kept in
// view. The API has no undo, so none is offered.
import { X } from "lucide-react";

import { ICON } from "@/theme/tokens/semantic";

import { Button } from "../ui/button";

export interface ChangeStripProps {
  /** `change_summary` from the latest refinement, shown as given. */
  changeSummary: readonly string[];
  /** `interpreted_query.original_query`; it never changes during refinement. */
  originalQuery: string;
  onDismiss: () => void;
}

export function ChangeStrip({ changeSummary, originalQuery, onDismiss }: ChangeStripProps) {
  if (changeSummary.length === 0) return null;
  return (
    <section aria-label="What changed" className="mx-1 mb-1 flex items-start gap-1 rounded-md border border-hairline bg-surface-raised p-1">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="text-meta text-muted">Refined “{originalQuery}”</p>
        <ul aria-live="polite" className="flex flex-col text-meta text-fg">
          {changeSummary.map((change) => (
            <li key={change}>{change}</li>
          ))}
        </ul>
      </div>
      <Button size="icon-sm" variant="quiet" aria-label="Dismiss what changed" onClick={onDismiss}>
        <X aria-hidden="true" {...ICON} />
      </Button>
    </section>
  );
}
