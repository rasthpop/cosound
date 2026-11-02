// Labels for the API's enums and codes. Each map covers the values the contract defines today; a
// value it doesn't know gets `humanize(code)`, a readable form of the code itself, never an
// invented meaning.
import type {
  ChangeEntry,
  ConstraintCheck,
  ConstraintStatus,
  EvidenceStatus,
  HardConstraint,
  InterpretedQuery,
  MatchStrength,
  NeighborMetric,
  RelationshipType,
  RetrievalSource,
} from "@/api/types";

import { formatDuration, humanize } from "./text";

const label = <K extends string>(labels: Partial<Record<K, string>>, value: K): string => labels[value] ?? humanize(value);

const EVIDENCE: Record<EvidenceStatus, string> = {
  audio_and_metadata: "Matched on sound and catalog data",
  metadata_only: "Matched on catalog data only",
  audio_only: "Matched on sound only",
};

/** The evidence a match rests on. */
export function evidenceLabel(status: EvidenceStatus): string {
  return label(EVIDENCE, status);
}

const SOURCES: Record<RetrievalSource, string> = {
  semantic: "sound",
  metadata: "catalog data",
  relationship: "catalog relationships",
};

/** "sound", "catalog data", … (for "Found through sound and catalog data"). */
export function retrievalSourceLabel(source: RetrievalSource): string {
  return label(SOURCES, source);
}

const ATTRIBUTES: Record<string, string> = {
  vocals: "Vocals",
  instrument: "Instrument",
  genre: "Genre",
  era: "Era",
  tempo: "Tempo",
  duration: "Duration",
};

/** "Vocals", "Era", …; unknown attributes are humanized. */
export function attributeLabel(attribute: string): string {
  return ATTRIBUTES[attribute] ?? humanize(attribute);
}

const FLAGS: Record<string, string> = {
  no_audio: "No audio analysis for this track",
  semantic_unavailable: "Sound-based matching was unavailable",
};

/** One `uncertainty_flags` entry as a sentence; `constraint_unknown:<attribute>` → "<Attribute> not verified". */
export function uncertaintyLabel(flag: string): string {
  const known = FLAGS[flag];
  if (known) return known;
  const [kind, attribute] = flag.split(":", 2);
  if (kind === "constraint_unknown" && attribute) return `${attributeLabel(attribute)} not verified`;
  return humanize(flag);
}

const STATUS: Record<ConstraintStatus, string> = {
  satisfied: "met",
  violated: "not met",
  unknown: "not verified",
};

/** "No vocals: not verified", "Genre Folk only: met". */
export function constraintCheckLabel(check: ConstraintCheck): string {
  return `${hardConstraintLabel({ ...check, range: null })}: ${label(STATUS, check.status)}`;
}

/** Wording for an open upper bound; ranges are inclusive (low ≤ value ≤ high). */
const AT_LEAST: Record<string, string> = { era: "or later", duration: "or longer", tempo: "or faster" };

function bound(attribute: string, value: number): string {
  if (attribute === "duration") return formatDuration(value) ?? String(value);
  if (attribute === "tempo") return `${value} BPM`;
  return String(value);
}

/** A hard constraint as the user would say it: "No vocals", "Folk only", "Era: 1990 or later". */
export function hardConstraintLabel(c: Pick<HardConstraint, "attribute" | "operator" | "value" | "range">): string {
  const name = attributeLabel(c.attribute);
  if (c.operator === "range") {
    const [low, high] = c.range ?? [null, null];
    if (low != null && high != null) return `${name}: ${bound(c.attribute, low)}–${bound(c.attribute, high)}`;
    if (low != null) return `${name}: ${bound(c.attribute, low)} ${AT_LEAST[c.attribute] ?? "or more"}`;
    if (high != null) return `${name}: up to ${bound(c.attribute, high)}`;
    return `${name}: any`;
  }
  if (c.attribute === "vocals") return c.operator === "excluded" ? "No vocals" : "With vocals";
  const subject = c.value ?? name;
  if (c.operator === "excluded") return `No ${subject}`;
  if (c.operator === "required") return `${subject} only`;
  return `${name} ${humanize(c.operator)}${c.value ? ` ${c.value}` : ""}`;
}

const VOCALS: Record<InterpretedQuery["vocal_preferences"], string | null> = {
  required: "Vocals required",
  preferred: "Vocals preferred",
  avoided: "Fewer vocals",
  excluded: "No vocals",
  unspecified: null,
};

/** `null` when the query said nothing about vocals. */
export function vocalPreferenceLabel(preference: InterpretedQuery["vocal_preferences"]): string | null {
  return preference in VOCALS ? (VOCALS[preference] ?? null) : humanize(preference);
}

const METRIC: Record<NeighborMetric, string> = {
  clap_cosine: "Nearby in sound",
  catalog_relationship: "Related in the catalog",
};

/** The heading for a neighbor list, from how the neighbors were found. */
export function neighborMetricLabel(metric: NeighborMetric): string {
  return label(METRIC, metric);
}

const NEIGHBOR_REASONS: Record<string, string> = {
  no_audio_embedding: "This track has no audio analysis, so these tracks are related through the catalog instead.",
};

/** Why neighbors fell back from sound to the catalog (`NeighborsResponse.reason`); `null` = no note. */
export function neighborReasonLabel(reason: string | null | undefined): string | null {
  if (!reason) return null;
  return NEIGHBOR_REASONS[reason] ?? humanize(reason);
}

const RELATIONSHIP: Record<RelationshipType, string> = {
  same_artist: "Same artist",
  same_label: "Same label",
  same_master: "Same master release",
  same_release: "Same release",
  shared_style: "Shared style",
};

export function relationshipLabel(type: RelationshipType): string {
  return label(RELATIONSHIP, type);
}

const ERRORS: Record<string, string> = {
  validation_error: "That request couldn't be read. Check the search and try again.",
  track_not_found: "That track isn't in the catalog.",
  session_not_found: "This search session has expired. Start a new search.",
  query_not_in_session: "This search session has changed. Start a new search.",
  track_not_in_results: "That track is no longer in the results. Refresh and try again.",
  stale_session_version: "The search changed in the meantime. Try again.",
  invalid_feedback_event: "That feedback couldn't be applied.",
  contradictory_constraints: "The search asks for opposite things. Edit your search.",
  projection_unavailable: "The map is unavailable. Search still works.",
  semantic_unavailable: "Sound-based matching is unavailable.",
  audio_missing: "No audio preview is available for this track.",
  network_error: "The server couldn't be reached. Check your connection and retry.",
  invalid_response: "The server sent a response that couldn't be read. Retry.",
  internal_error: "Something went wrong on the server. Retry.",
};

/** A human message for an `error.code`; unknown codes get a generic message, never a stack trace. */
export function errorMessage(code: string | null | undefined): string {
  return (code && ERRORS[code]) || "Something went wrong. Retry.";
}

const BANDS: Record<MatchStrength, string> = { strong: "Strong", partial: "Partial", weak: "Weak" };

/** A score band in words; `null` → "not available" (a signal that was not computed is never 0). */
export function bandLabel(band: MatchStrength | null): string {
  return band === null ? "not available" : label(BANDS, band);
}

/** "Strong match" / "Partial match"; `null` for weak or missing bands, which show no badge. */
export function matchBandLabel(band: MatchStrength | null | undefined): string | null {
  if (band === "strong") return "Strong match";
  if (band === "partial") return "Partial match";
  return null;
}

const quoted = (title: string | null) => (title ? `“${title}”` : "a track");

/**
 * One structured "what changed" entry in words. Tracks are named by their catalog title; with no
 * title the entry says "a track", never the raw track id.
 */
export function changeLabel(change: ChangeEntry): string {
  const term = change.value ?? (change.attribute ? attributeLabel(change.attribute).toLowerCase() : "");
  switch (change.kind) {
    case "reference_added":
      return `More like ${quoted(change.title)}`;
    case "negative_reference_added":
      return `Less like ${quoted(change.title)}`;
    case "excluded":
      return change.attribute === "instrument"
        ? `Removed ${quoted(change.title)} (wrong ${change.value ?? "instrument"})`
        : `Removed ${quoted(change.title)}`;
    case "preference_added":
      return `Added ${term}`;
    case "preference_raised":
      return `More ${term}`;
    case "preference_lowered":
      return change.attribute === "vocals" ? "Fewer vocals" : `Less ${term}`;
    case "preference_removed":
      return `Dropped ${term}`;
    case "negative_added":
      return `Avoiding ${term}`;
    case "negative_removed":
      return `No longer avoiding ${term}`;
    case "constraint_added":
      return `Now required: ${hardConstraintLabel({
        attribute: (change.attribute ?? "constraint") as HardConstraint["attribute"],
        operator: (change.operator ?? "required") as HardConstraint["operator"],
        value: change.value,
        range: null,
      })}`;
    case "rejected":
      return "That feedback was not applied";
    case "needs_clarification":
      return change.value ? `Needs clarification: ${change.value}` : "Needs clarification";
    default:
      return [humanize(change.kind), change.value].filter(Boolean).join(": ");
  }
}
