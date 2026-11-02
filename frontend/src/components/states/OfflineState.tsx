// No response at all (`ApiError.kind === "network"`): the user's connection or the server may be
// down, so the copy doesn't claim which. Retry, and the typed query is kept.
import { WifiOff } from "lucide-react";

import { Button } from "../ui/button";
import { StateMessage } from "./StateMessage";

export interface OfflineStateProps {
  /** The query the user typed; it stays in the search bar. */
  query?: string | null;
  onRetry?: () => void;
}

export function OfflineState({ query, onRetry }: OfflineStateProps) {
  return (
    <StateMessage
      icon={WifiOff}
      tone="error"
      role="alert"
      title="Can't reach the server"
      actions={
        onRetry && (
          <Button size="sm" onClick={onRetry}>
            Retry
          </Button>
        )
      }
    >
      <p>The server couldn't be reached.{query ? ` Your search “${query}” is kept.` : ""}</p>
    </StateMessage>
  );
}
