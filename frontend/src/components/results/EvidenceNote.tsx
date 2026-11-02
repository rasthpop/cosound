// What a match rests on (ux-states-and-evidence §3): the evidence status when it isn't the full
// "sound and catalog" picture, every uncertainty flag, and how the track was found.
import { Info } from "lucide-react";

import type { TrackResult } from "@/api/types";
import { ICON } from "@/theme/tokens/semantic";

import { evidenceLabel, retrievalSourceLabel, uncertaintyLabel } from "../format/labels";

export type EvidenceNoteProps = Pick<TrackResult, "evidence_status" | "uncertainty_flags" | "retrieval_sources">;

/** Renders nothing when the match rests on sound and catalog data with no open questions. */
export function EvidenceNote({ evidence_status, uncertainty_flags, retrieval_sources }: EvidenceNoteProps) {
  const notes = [
    ...(evidence_status === "audio_and_metadata" ? [] : [evidenceLabel(evidence_status)]),
    ...uncertainty_flags.map(uncertaintyLabel),
  ];
  const unique = [...new Set(notes)];
  if (unique.length === 0) return null;
  const sources = retrieval_sources.map(retrievalSourceLabel);
  return (
    <p className="flex items-start gap-0.5 text-meta text-muted">
      <Info aria-hidden="true" className="mt-0.5 shrink-0 text-state-warning" {...ICON} />
      <span>
        {unique.join(" · ")}
        {sources.length > 0 && <span className="sr-only"> Found through {sources.join(" and ")}.</span>}
      </span>
    </p>
  );
}
