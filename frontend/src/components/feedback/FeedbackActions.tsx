// Track feedback (ui.md §4.2, ux-states-and-evidence §4): each gesture maps 1:1 to one event type.
// The view only acknowledges the gesture (pending → applied / rejected / error); the plate itself
// changes when the server's refreshed results arrive.
import { ThumbsDown, ThumbsUp, X } from "lucide-react";

import { ICON } from "@/theme/tokens/semantic";

import { Button } from "../ui/button";
import { cn } from "../ui/cn";
import { InstrumentPicker } from "./InstrumentPicker";
import type { FeedbackStatus, TrackFeedback, TrackFeedbackType } from "./types";

const GESTURES = [
  { eventType: "MORE_LIKE_THIS", label: "More like this", Icon: ThumbsUp },
  { eventType: "LESS_LIKE_THIS", label: "Less like this", Icon: ThumbsDown },
  { eventType: "NOT_RELEVANT", label: "Not relevant", Icon: X },
] as const satisfies ReadonlyArray<{ eventType: TrackFeedbackType; label: string; Icon: unknown }>;

export interface FeedbackActionsProps {
  trackId: string;
  title: string;
  status?: FeedbackStatus;
  /** The gesture the status belongs to. */
  lastEvent?: TrackFeedbackType | null;
  /** `reason` when rejected, an error message when failed. */
  message?: string | null;
  /** Instruments from the interpreted query; enables "Wrong instrument…". */
  instruments?: readonly string[];
  /** `labels` shows text next to the icons (details drawer); `icons` is the compact row form. */
  layout?: "icons" | "labels";
  onFeedback: (feedback: TrackFeedback) => void;
}

const STATUS_TEXT: Record<Exclude<FeedbackStatus, "idle">, string> = {
  pending: "Sending…",
  applied: "Applied",
  rejected: "Not applied",
  error: "Couldn't send",
};

export function FeedbackActions({
  trackId,
  title,
  status = "idle",
  lastEvent = null,
  message = null,
  instruments = [],
  layout = "icons",
  onFeedback,
}: FeedbackActionsProps) {
  const pending = status === "pending";
  return (
    <div className={cn("flex gap-0.5", layout === "icons" ? "items-center" : "flex-col items-start")}>
      <div role="group" aria-label={`Feedback on ${title}`} className="flex flex-wrap items-center gap-0.5">
        {GESTURES.map(({ eventType, label, Icon }) => (
          <Button
            key={eventType}
            size={layout === "icons" ? "icon-sm" : "sm"}
            variant="quiet"
            aria-label={layout === "icons" ? `${label}: ${title}` : undefined}
            aria-busy={pending && lastEvent === eventType}
            disabled={pending}
            className={cn(lastEvent === eventType && status === "applied" && "text-fg")}
            onClick={() => onFeedback({ trackId, eventType })}
          >
            <Icon aria-hidden="true" {...ICON} />
            {layout === "labels" && label}
          </Button>
        ))}
        <InstrumentPicker
          instruments={instruments}
          title={title}
          disabled={pending}
          compact={layout === "icons"}
          onPick={(instrument) => onFeedback({ trackId, eventType: "WRONG_INSTRUMENT", attribute: "instrument", value: instrument })}
        />
      </div>
      {status !== "idle" && (
        <p
          role={status === "error" ? "alert" : "status"}
          className={cn("text-meta", status === "error" || status === "rejected" ? "text-fg" : "text-muted")}
        >
          {STATUS_TEXT[status]}
          {message ? `: ${message}` : ""}
        </p>
      )}
    </div>
  );
}
