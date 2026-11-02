// No response at all (`ApiError.kind === "network"`): retry, and the typed query is kept.
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
      title="You're offline"
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
