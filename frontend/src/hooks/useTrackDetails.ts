// Details (and optionally original-space neighbors) of one track, by id.
//
// - In-memory cache keyed by track id: going back to a track costs no request.
// - The cache belongs to one projection version: pass `projectionVersion` (from useMusicMap)
//   and a new version drops every cached entry, since coordinates may have changed.
// - Changing the id aborts the request for the previous one.
import { useCallback, useEffect, useState } from "react";

import { apiClient, isAbortError, isApiError, type ApiClient } from "../api/client";
import type { ApiError, NeighborsResponse, TrackDetail } from "../api/types";
import { toApiError, type RequestStatus } from "./status";

export interface UseTrackDetailsOptions {
  client?: ApiClient;
  /** Also fetch `GET /api/tracks/{id}/neighbors`. */
  withNeighbors?: boolean;
  /** Number of neighbors (API default when omitted). */
  k?: number;
  /** The map's projection version; a change invalidates the cache. */
  projectionVersion?: string | null;
}

export interface TrackDetailsState {
  status: RequestStatus;
  detail: TrackDetail | null;
  /** `null` when not requested, not loaded yet, or failed (see `neighborsError`). */
  neighbors: NeighborsResponse | null;
  error: ApiError | null;
  /** Neighbors can fail while details succeed (e.g. a transient error). */
  neighborsError: ApiError | null;
  /** Drop the cached entry for the current id and fetch it again. */
  reload: () => void;
}

interface Entry {
  detail: TrackDetail;
  neighbors: NeighborsResponse | null;
  neighborsError: ApiError | null;
  withNeighbors: boolean;
}

interface Cache {
  version: string | null;
  entries: ReadonlyMap<string, Entry>;
}

const asApiError = (cause: unknown): ApiError => (isApiError(cause) ? cause.toJSON() : toApiError(cause));

export function useTrackDetails(trackId: string | null, options: UseTrackDetailsOptions = {}): TrackDetailsState {
  const client = options.client ?? apiClient;
  const withNeighbors = options.withNeighbors ?? false;
  const k = options.k;
  const version = options.projectionVersion ?? null;

  const [cache, setCache] = useState<Cache>({ version, entries: new Map() });
  const [failure, setFailure] = useState<{ trackId: string; error: ApiError } | null>(null);

  const entries = cache.version === version ? cache.entries : new Map<string, Entry>();
  const entry = trackId === null ? undefined : entries.get(trackId);
  const needsFetch = trackId !== null && (!entry || (withNeighbors && !entry.withNeighbors));
  const failed = failure !== null && failure.trackId === trackId && needsFetch;

  useEffect(() => {
    if (trackId === null || !needsFetch || failed) return;
    const controller = new AbortController();
    const signal = controller.signal;
    const neighborsRequest = withNeighbors
      ? client.getNeighbors(trackId, k === undefined ? { signal } : { signal, k })
      : null;
    void (async () => {
      try {
        const detail = await client.getTrack(trackId, { signal });
        let neighbors: NeighborsResponse | null = null;
        let neighborsError: ApiError | null = null;
        if (neighborsRequest) {
          try {
            neighbors = await neighborsRequest;
          } catch (cause) {
            if (isAbortError(cause)) return;
            neighborsError = asApiError(cause);
          }
        }
        setCache((current) => {
          const base = current.version === version ? current.entries : new Map<string, Entry>();
          const next = new Map(base);
          next.set(trackId, { detail, neighbors, neighborsError, withNeighbors });
          return { version, entries: next };
        });
      } catch (cause) {
        neighborsRequest?.catch(() => undefined);
        if (isAbortError(cause)) return;
        setFailure({ trackId, error: asApiError(cause) });
      }
    })();
    return () => controller.abort();
  }, [client, failed, k, needsFetch, trackId, version, withNeighbors]);

  const reload = useCallback(() => {
    if (trackId === null) return;
    setFailure(null);
    setCache((current) => {
      const next = new Map(current.entries);
      next.delete(trackId);
      return { ...current, entries: next };
    });
  }, [trackId]);

  let status: RequestStatus = "idle";
  if (trackId !== null) status = failed ? "error" : needsFetch ? "loading" : "success";
  return {
    status,
    detail: entry?.detail ?? null,
    neighbors: entry?.neighbors ?? null,
    error: failed ? failure.error : null,
    neighborsError: entry?.neighborsError ?? null,
    reload,
  };
}
