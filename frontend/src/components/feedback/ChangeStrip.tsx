// "What changed" after feedback (ui.md §4.2): a dismissible list, with the original query kept in
// view. Structured `changes` are rendered when present (track titles, attributes); otherwise the
// `change_summary` strings. Feedback the backend did not apply (`accepted: false`) shows its
// `reason`; a failed request shows why. The API has no undo, so none is offered.
import { X } from "lucide-react";

import type { ChangeEntry } from "@/api/types";
import { ICON } from "@/theme/tokens/semantic";

import { changeLabel } from "../format/labels";
import { Button } from "../ui/button";

export interface ChangeStripProps {
  /** `change_summary` from the latest refinement, shown as given. */
  changeSummary: readonly string[];
  /** Structured `changes`; preferred over the strings when non-empty. */
  changes?: readonly ChangeEntry[];
  /** `interpreted_query.original_query`; it never changes during refinement. */
  originalQuery: string;
  /** `rejected`: `accepted: false`; `error`: the request failed. Default `applied`. */
  status?: "applied" | "rejected" | "error";
  /** The backend's `reason` (rejected) or a human error message (error), shown as given. */
  message?: string | null;
  onDismiss: () => void;
}

const NOT_APPLIED = { rejected: "Not applied", error: "Couldn't send the refinement" } as const;

export function ChangeStrip({ changeSummary, changes = [], originalQuery, status = "applied", message = null, onDismiss }: ChangeStripProps) {
  const failed = status !== "applied";
  // a rejection's own entry ("not applied") is replaced by the reason line below
  const lines = failed ? [] : changes.length > 0 ? [...new Set(changes.map(changeLabel))] : changeSummary;
  if (lines.length === 0 && !failed) return null;
  return (
    <section aria-label="What changed" className="mx-1 mb-1 flex items-start gap-1 rounded-md border border-hairline bg-surface-raised p-1">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="text-meta text-muted">Refined “{originalQuery}”</p>
        {lines.length > 0 && (
          <ul aria-live="polite" className="flex flex-col text-meta text-fg">
            {lines.map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
        )}
        {failed && (
          <p role={status === "error" ? "alert" : "status"} className="text-meta text-fg">
            {NOT_APPLIED[status]}
            {message ? `: ${message}` : ""}
          </p>
        )}
      </div>
      <Button size="icon-sm" variant="quiet" aria-label="Dismiss what changed" onClick={onDismiss}>
        <X aria-hidden="true" {...ICON} />
      </Button>
    </section>
  );
}
