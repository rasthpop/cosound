// Feedback payloads emitted by the views; the same shape as useTrackFeedback's FeedbackInput, so
// the container passes them straight to `submit`.
import type { FeedbackType } from "@/api/types";

export type TrackFeedbackType = Extract<FeedbackType, "MORE_LIKE_THIS" | "LESS_LIKE_THIS" | "NOT_RELEVANT" | "WRONG_INSTRUMENT">;

export interface TrackFeedback {
  trackId: string;
  eventType: TrackFeedbackType;
  /** WRONG_INSTRUMENT: `"instrument"`. */
  attribute?: string;
  /** WRONG_INSTRUMENT: the instrument named in the query (`"flute"`). */
  value?: string;
}

/**
 * The state of one track's feedback, from the container (useTrackFeedback.byTrack):
 * idle · pending (in flight) · applied (accepted) · rejected (`accepted: false` + reason) · error.
 */
export type FeedbackStatus = "idle" | "pending" | "applied" | "rejected" | "error";
