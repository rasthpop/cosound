// Shared request-state vocabulary for the hooks.
import type { ApiError } from "../api/types";

export type RequestStatus = "idle" | "loading" | "success" | "error";

/** An ApiError for failures that did not come from the API client (should not happen). */
export function toApiError(cause: unknown): ApiError {
  return {
    kind: "network",
    code: "unexpected_error",
    message: cause instanceof Error ? cause.message : String(cause),
    status: null,
    details: {},
  };
}
