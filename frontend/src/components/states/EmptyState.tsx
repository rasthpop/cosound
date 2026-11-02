// `outcome: "ok"` with no results: say nothing matched and suggest broadening.
import { SearchX } from "lucide-react";

import { Button } from "../ui/button";
import { StateMessage } from "./StateMessage";

export interface EmptyStateProps {
  /** The query as the user typed it, echoed back; omitted when unknown. */
  query?: string | null;
  onEditQuery?: () => void;
}

export function EmptyState({ query, onEditQuery }: EmptyStateProps) {
  return (
    <StateMessage
      icon={SearchX}
      title="No tracks matched"
      role="status"
      actions={
        onEditQuery && (
          <Button size="sm" onClick={onEditQuery}>
            Edit your search
          </Button>
        )
      }
    >
      {query && <p>Nothing in the catalog matched “{query}”.</p>}
      <p>Try fewer or broader words: a mood, an instrument or a genre.</p>
    </StateMessage>
  );
}
