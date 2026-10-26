// Which capabilities the backend has right now, before any search runs (GET /api/health).
//
// - Fetched once on mount; no polling. `reload()` asks again (e.g. a status pill's retry) and
//   keeps the last answer visible while it runs.
// - A failed request leaves `capabilities` null: an offline client (`error.kind === "network"`)
//   knows nothing about the backend, so it never guesses a capability.
// - After a search, `SearchResponse.capabilities` is the fresher source for that plate.
import { useCallback, useEffect, useState } from "react";

import { apiClient, isAbortError, isApiError, type ApiClient } from "../api/client";
import type { ApiError, Capabilities, HealthResponse } from "../api/types";
import { toApiError, type RequestStatus } from "./status";

export interface UseSystemStatusOptions {
  client?: ApiClient;
}

export interface SystemStatus {
  status: RequestStatus;
  /** `null` until the first successful response, and after a failure. */
  capabilities: Capabilities | null;
  /** Why semantic search or the map is unavailable (e.g. `clap_checkpoint_missing`); `null` when available. */
  reasons: { semantic: string | null; map: string | null };
  error: ApiError | null;
  /** Fetch the status again. */
  reload: () => void;
}

const NO_REASONS = { semantic: null, map: null };

export function useSystemStatus(options: UseSystemStatusOptions = {}): SystemStatus {
  const client = options.client ?? apiClient;
  const [attempt, setAttempt] = useState(0);
  // the latest settled answer; kept while a reload runs, so the status doesn't flicker
  const [settled, setSettled] = useState<{
    attempt: number;
    health: HealthResponse | null;
    error: ApiError | null;
  } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const health = await client.health({ signal: controller.signal });
        setSettled({ attempt, health, error: null });
      } catch (cause) {
        if (isAbortError(cause)) return;
        setSettled({ attempt, health: null, error: isApiError(cause) ? cause.toJSON() : toApiError(cause) });
      }
    })();
    return () => controller.abort();
  }, [attempt, client]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  const health = settled?.health ?? null;
  let status: RequestStatus = "loading";
  if (settled?.attempt === attempt) status = settled.error ? "error" : "success";
  return {
    status,
    capabilities: health?.capabilities ?? null,
    reasons: health ? { semantic: health.semantic_reason, map: health.map_reason } : NO_REASONS,
    error: settled?.error ?? null,
    reload,
  };
}
