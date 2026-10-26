// Feedback on the current plate. Session and query ids come from `useMusicSearch` (passed in,
// not global); a refreshed plate in the response is pushed back into that search state.
// Submission state is kept per track, so several cards can be pending at once.
import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient, isAbortError, isApiError, type ApiClient } from "../api/client";
import type { ApiError, FeedbackRequest, FeedbackResponse, FeedbackType } from "../api/types";
import { toApiError, type RequestStatus } from "./status";
import type { MusicSearch } from "./useMusicSearch";

/** Key used for feedback that names no track (free text about the whole plate). */
export const PLATE_KEY = "__plate__";

export interface FeedbackInput {
  trackId?: string | null;
  eventType?: FeedbackType | null;
  attribute?: string | null;
  value?: boolean | number | string | null;
  freeText?: string | null;
}

export interface FeedbackCallOptions {
  /** Ask for the refreshed plate and show it through `useMusicSearch`. */
  refresh?: boolean;
  limit?: number;
}

export interface FeedbackState {
  status: RequestStatus;
  error: ApiError | null;
  response: FeedbackResponse | null;
}

export interface TrackFeedback {
  /** State per track id (or PLATE_KEY); tracks never submitted are absent. */
  byTrack: Readonly<Record<string, FeedbackState>>;
  isPending: (trackId?: string | null) => boolean;
  /** The most recent response (accepted or not). */
  lastResponse: FeedbackResponse | null;
  /** Resolves to the response, or `null` when the request failed (see `byTrack[..].error`). */
  submit: (input: FeedbackInput, options?: FeedbackCallOptions) => Promise<FeedbackResponse | null>;
}

export interface UseTrackFeedbackOptions {
  client?: ApiClient;
}

type SearchLink = Pick<MusicSearch, "sessionId" | "queryId" | "applyRefreshed">;

const NO_SEARCH: ApiError = {
  kind: "http",
  code: "no_active_search",
  message: "Feedback needs a search result to refer to.",
  status: null,
  details: {},
};

export function useTrackFeedback(search: SearchLink, options: UseTrackFeedbackOptions = {}): TrackFeedback {
  const client = options.client ?? apiClient;
  const [byTrack, setByTrack] = useState<Record<string, FeedbackState>>({});
  const [lastResponse, setLastResponse] = useState<FeedbackResponse | null>(null);
  const controllers = useRef(new Set<AbortController>());
  const { sessionId, queryId, applyRefreshed } = search;

  useEffect(() => {
    const active = controllers.current;
    return () => {
      for (const controller of active) controller.abort();
    };
  }, []);

  const update = useCallback((key: string, state: FeedbackState) => {
    setByTrack((current) => ({ ...current, [key]: state }));
  }, []);

  const submit = useCallback(
    async (input: FeedbackInput, call: FeedbackCallOptions = {}): Promise<FeedbackResponse | null> => {
      const key = input.trackId ?? PLATE_KEY;
      if (sessionId === null || queryId === null) {
        update(key, { status: "error", error: NO_SEARCH, response: null });
        return null;
      }
      const request: FeedbackRequest = { session_id: sessionId, query_id: queryId };
      if (input.trackId) request.track_id = input.trackId;
      if (input.eventType) request.event_type = input.eventType;
      if (input.attribute != null) request.attribute = input.attribute;
      if (input.value != null) request.value = input.value;
      if (input.freeText) request.free_text = input.freeText;
      if (call.refresh) request.refresh = true;
      if (call.limit !== undefined) request.limit = call.limit;

      const controller = new AbortController();
      controllers.current.add(controller);
      update(key, { status: "loading", error: null, response: null });
      try {
        const response = await client.submitFeedback(request, { signal: controller.signal });
        update(key, { status: "success", error: null, response });
        setLastResponse(response);
        if (response.refreshed) applyRefreshed(response.refreshed);
        return response;
      } catch (cause) {
        if (isAbortError(cause)) return null;
        update(key, {
          status: "error",
          error: isApiError(cause) ? cause.toJSON() : toApiError(cause),
          response: null,
        });
        return null;
      } finally {
        controllers.current.delete(controller);
      }
    },
    [applyRefreshed, client, queryId, sessionId, update],
  );

  const isPending = useCallback(
    (trackId?: string | null) => byTrack[trackId ?? PLATE_KEY]?.status === "loading",
    [byTrack],
  );

  return { byTrack, isPending, lastResponse, submit };
}
