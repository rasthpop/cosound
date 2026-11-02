// Feedback wiring helpers for the Discover screen (ui.md §4.1–4.2, D1/D2): translate the hook's
// per-track state into what the feedback views show. Pure; no decisions about relevance.
import type { FeedbackResponse, InterpretedQuery } from "@/api/types";
import type { FeedbackStatus } from "@/components/feedback/types";
import { errorMessage } from "@/components/format/labels";
import type { FeedbackState } from "@/hooks";

/** The view's acknowledgement for one submission: pending → applied / rejected / error. */
export function feedbackStatus(state: FeedbackState | undefined): FeedbackStatus {
  if (!state) return "idle";
  if (state.status === "loading") return "pending";
  if (state.status === "error") return "error";
  if (state.status === "success" && state.response) return state.response.accepted ? "applied" : "rejected";
  return "idle";
}

/** The backend's `reason` when it did not apply the feedback, a human message when it failed. */
export function feedbackMessage(state: FeedbackState | undefined): string | null {
  if (!state) return null;
  if (state.status === "error") return errorMessage(state.error?.code);
  if (state.response && !state.response.accepted) return state.response.reason;
  return null;
}

/** Instruments named in the query: the choices for "Wrong instrument…". */
export function queryInstruments(query: InterpretedQuery | null | undefined): string[] {
  return (query?.instrument_preferences ?? []).map((p) => p.value);
}

/** What the "what changed" strip shows for the latest refinement. */
export interface StripState {
  status: "applied" | "rejected" | "error";
  response: FeedbackResponse | null;
  message: string | null;
}

export function stripFor(state: FeedbackState | undefined): StripState | null {
  const status = feedbackStatus(state);
  if (status === "applied" || status === "rejected" || status === "error") {
    return { status, response: state?.response ?? null, message: feedbackMessage(state) };
  }
  return null;
}
