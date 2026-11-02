// A failed request: a human message chosen by `error.code`, a retry, and no technical detail.
import { TriangleAlert } from "lucide-react";

import type { ApiError } from "@/api/types";

import { errorMessage } from "../format/labels";
import { Button } from "../ui/button";
import { StateMessage } from "./StateMessage";

export interface ErrorStateProps {
  error: Pick<ApiError, "code"> | null;
  onRetry?: () => void;
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <StateMessage
      icon={TriangleAlert}
      tone="error"
      role="alert"
      title="Search didn't work"
      actions={
        onRetry && (
          <Button size="sm" onClick={onRetry}>
            Retry
          </Button>
        )
      }
    >
      <p>{errorMessage(error?.code)}</p>
    </StateMessage>
  );
}
