// The details drawer (ui.md §4.4, ADR-0003). Desktop: a right-hand 400 px sheet that is
// non-modal, so the map stays usable, yet Tab loops inside it; Esc or ✕ closes. Below 1024 px:
// a full-height modal sheet. Everything shown comes from the API as is; absent fields render
// nothing.
import { ExternalLink } from "lucide-react";
import type { KeyboardEvent, ReactNode } from "react";

import type { ApiError, TrackDetail } from "@/api/types";
import { ICON } from "@/theme/tokens/semantic";

import { AudioPlayer } from "../audio/AudioPlayer";
import { errorMessage } from "../format/labels";
import { formatArtists, formatDuration } from "../format/text";
import { Badge } from "../ui/badge";
import { Separator } from "../ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "../ui/sheet";
import { Skeleton } from "../ui/skeleton";

export type DetailsStatus = "loading" | "ready" | "error";

export interface TrackDetailsDrawerProps {
  open: boolean;
  /** Esc, ✕ or (mobile) the overlay. */
  onClose: () => void;
  /** Called after closing; `preventDefault()` it to move focus back to the row or map point. */
  onCloseAutoFocus?: (event: Event) => void;
  variant?: "desktop" | "mobile";
  status: DetailsStatus;
  detail: TrackDetail | null;
  /** Set when `status === "error"`; `track_not_found` gets its own message. */
  error?: Pick<ApiError, "code"> | null;
  /** Playable URL for `detail.preview_url`, resolved by the container. */
  playUrl: string | null;
  /** From the result row when the track was opened from the plate; absent → nothing shown. */
  description?: string | null;
  matchReasons?: readonly string[];
  /** Feedback actions (FeedbackActions, layout "labels"). */
  actions?: ReactNode;
  /** Score bands and other evidence (U02.T07). */
  evidence?: ReactNode;
  /** NeighborList and RelatedTracks. */
  related?: ReactNode;
}

/** Loop Tab inside a non-modal panel without blocking clicks outside it. */
function loopTab(event: KeyboardEvent<HTMLElement>) {
  if (event.key !== "Tab") return;
  const focusable = [
    ...event.currentTarget.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), audio[controls], [tabindex]:not([tabindex="-1"])',
    ),
  ].filter((el) => !el.hasAttribute("hidden"));
  const first = focusable[0];
  const last = focusable.at(-1);
  if (!first || !last) return;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function Facts({ detail }: { detail: TrackDetail }) {
  const duration = formatDuration(detail.duration_seconds);
  const release = detail.release ? `${detail.release.title}${detail.release.year ? ` (${detail.release.year})` : ""}` : null;
  const facts = [
    ["Release", release],
    ["Year", detail.year === null ? null : String(detail.year)],
    ["Duration", duration],
  ].filter((f): f is [string, string] => f[1] !== null);
  const tags = [...detail.genres, ...detail.styles, ...detail.tags];
  return (
    <>
      {tags.length > 0 && (
        <ul aria-label="Genres, styles and tags" className="flex flex-wrap gap-0.5">
          {[...new Set(tags)].map((t) => (
            <li key={t}>
              <Badge>{t}</Badge>
            </li>
          ))}
        </ul>
      )}
      {facts.length > 0 && (
        <dl className="flex flex-col text-meta">
          {facts.map(([k, v]) => (
            <div key={k} className="flex gap-1.5">
              <dt className="w-8 shrink-0 text-muted">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </>
  );
}

export function TrackDetailsDrawer({
  open,
  onClose,
  onCloseAutoFocus,
  variant = "desktop",
  status,
  detail,
  error = null,
  playUrl,
  description = null,
  matchReasons = [],
  actions,
  evidence,
  related,
}: TrackDetailsDrawerProps) {
  const desktop = variant === "desktop";
  const artists = detail ? formatArtists(detail.artists) : null;
  const reasons = matchReasons.filter((r) => r.trim());
  return (
    <Sheet open={open} modal={!desktop} onOpenChange={(next) => !next && onClose()}>
      <SheetContent
        side="right"
        overlay={!desktop}
        onKeyDown={desktop ? loopTab : undefined}
        // non-modal: clicking the map or a row must not close the drawer
        onInteractOutside={desktop ? (e) => e.preventDefault() : undefined}
        {...(onCloseAutoFocus ? { onCloseAutoFocus } : {})}
        closeLabel="Close details"
        className="overflow-y-auto"
      >
        {status === "loading" && (
          <div aria-busy="true" className="flex flex-col gap-1">
            <SheetTitle className="sr-only">Loading track details</SheetTitle>
            <SheetDescription className="sr-only">The track's details are loading.</SheetDescription>
            <Skeleton className="h-3 w-30" />
            <Skeleton className="h-2 w-20" />
            <Skeleton className="h-5 w-full" />
          </div>
        )}
        {status === "error" && (
          <div role="alert" className="flex flex-col gap-0.5 pr-4">
            <SheetTitle>{error?.code === "track_not_found" ? "Track not found" : "Details unavailable"}</SheetTitle>
            <SheetDescription>{errorMessage(error?.code)}</SheetDescription>
          </div>
        )}
        {status === "ready" && detail && (
          <>
            <SheetHeader>
              <SheetTitle>{detail.title}</SheetTitle>
              <SheetDescription>{artists ?? "Track details"}</SheetDescription>
            </SheetHeader>
            <Facts detail={detail} />
            <AudioPlayer
              src={playUrl}
              title={detail.title}
              license={detail.audio?.license ?? null}
              clipSeconds={detail.audio?.duration_seconds ?? null}
            />
            {description && <p className="text-body">{description}</p>}
            {reasons.length > 0 && (
              <ul aria-label="Why it matched" className="flex list-disc flex-col pl-2 text-meta text-muted">
                {reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
            {evidence}
            {detail.source_url && (
              <a
                href={detail.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex w-fit items-center gap-0.5 text-meta text-fg underline decoration-border-strong underline-offset-4 hover:decoration-accent"
              >
                Open on FMA
                <ExternalLink aria-hidden="true" {...ICON} />
              </a>
            )}
            {actions}
            {related && (
              <>
                <Separator />
                {related}
              </>
            )}
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
