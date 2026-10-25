// Search state: the current plate, its session and query ids, request status and errors.
//
// - A new search cancels the one in flight; responses from older requests are dropped even if
//   they arrive later (request sequence), so a stale plate never overwrites a newer one.
// - The session id is kept across searches (follow-ups refine the same session) until
//   `reset()` or `search(q, { newSession: true })`.
// - While a new request runs, the previous plate stays in `data` (`isRefreshing`).
import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient, isAbortError, isApiError, type ApiClient } from "../api/client";
import type { ApiError, SearchRequest, SearchResponse } from "../api/types";
import { toApiError, type RequestStatus } from "./status";

export interface UseMusicSearchOptions {
  client?: ApiClient;
  /** Plate size when `search()` is called without one (API default otherwise). */
  limit?: number;
}

export interface SearchCallOptions {
  limit?: number;
  /** Start a new session instead of continuing the current one. */
  newSession?: boolean;
}

export interface MusicSearch {
  status: RequestStatus;
  /** The latest plate (kept while a newer request is loading or after it failed). */
  data: SearchResponse | null;
  error: ApiError | null;
  sessionId: string | null;
  queryId: string | null;
  /** The text of the last search sent. */
  lastQuery: string | null;
  /** A request is running and an older plate is still shown. */
  isRefreshing: boolean;
  /** Run a search; resolves to the response, or `null` if it failed or was superseded. */
  search: (query: string, options?: SearchCallOptions) => Promise<SearchResponse | null>;
  /** Re-run the last search in the same session (e.g. after feedback sent without refresh). */
  refresh: () => Promise<SearchResponse | null>;
  /** Show a plate obtained elsewhere (a feedback response's `refreshed`). */
  applyRefreshed: (response: SearchResponse) => void;
  /** Forget the plate and the session. */
  reset: () => void;
}

export function useMusicSearch(options: UseMusicSearchOptions = {}): MusicSearch {
  const client = options.client ?? apiClient;
  const defaultLimit = options.limit;

  const [status, setStatus] = useState<RequestStatus>("idle");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [lastQuery, setLastQuery] = useState<string | null>(null);

  const sequence = useRef(0);
  const inFlight = useRef<AbortController | null>(null);
  const session = useRef<string | null>(null);
  const lastRequest = useRef<SearchRequest | null>(null);

  const cancel = useCallback(() => {
    inFlight.current?.abort();
    inFlight.current = null;
  }, []);

  useEffect(() => cancel, [cancel]);

  const run = useCallback(
    async (request: SearchRequest): Promise<SearchResponse | null> => {
      cancel();
      const controller = new AbortController();
      inFlight.current = controller;
      const id = ++sequence.current;
      lastRequest.current = request;
      setLastQuery(request.query);
      setStatus("loading");
      setError(null);
      try {
        const response = await client.search(request, { signal: controller.signal });
        if (id !== sequence.current) return null; // superseded while in flight
        session.current = response.session_id;
        setData(response);
        setStatus("success");
        return response;
      } catch (cause) {
        if (id !== sequence.current || isAbortError(cause)) return null;
        setError(isApiError(cause) ? cause.toJSON() : toApiError(cause));
        setStatus("error");
        return null;
      } finally {
        if (inFlight.current === controller) inFlight.current = null;
      }
    },
    [cancel, client],
  );

  const search = useCallback(
    (query: string, call: SearchCallOptions = {}) => {
      if (call.newSession) session.current = null;
      const request: SearchRequest = { query, session_id: session.current };
      const limit = call.limit ?? defaultLimit;
      if (limit !== undefined) request.limit = limit;
      return run(request);
    },
    [defaultLimit, run],
  );

  const refresh = useCallback(() => {
    const previous = lastRequest.current;
    if (previous === null) return Promise.resolve(null);
    return run({ ...previous, session_id: session.current });
  }, [run]);

  const applyRefreshed = useCallback(
    (response: SearchResponse) => {
      cancel();
      sequence.current += 1; // anything still in flight is now stale
      session.current = response.session_id;
      setData(response);
      setError(null);
      setStatus("success");
    },
    [cancel],
  );

  const reset = useCallback(() => {
    cancel();
    sequence.current += 1;
    session.current = null;
    lastRequest.current = null;
    setData(null);
    setError(null);
    setLastQuery(null);
    setStatus("idle");
  }, [cancel]);

  return {
    status,
    data,
    error,
    sessionId: data?.session_id ?? null,
    queryId: data?.query_id ?? null,
    lastQuery,
    isRefreshing: status === "loading" && data !== null,
    search,
    refresh,
    applyRefreshed,
    reset,
  };
}
