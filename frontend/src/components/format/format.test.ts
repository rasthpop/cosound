import { describe, expect, it } from "vitest";

import type { ConstraintCheck, EvidenceStatus, NeighborMetric, RelationshipType } from "@/api/types";

import {
  attributeLabel,
  constraintCheckLabel,
  errorMessage,
  evidenceLabel,
  hardConstraintLabel,
  neighborMetricLabel,
  relationshipLabel,
  retrievalSourceLabel,
  uncertaintyLabel,
  vocalPreferenceLabel,
} from "./labels";
import { formatArtists, formatDuration, formatResultCount, humanize } from "./text";

describe("text formatters", () => {
  it("joins artists and returns null when there are none", () => {
    expect(formatArtists([{ name: "A" }, { name: "B" }])).toBe("A, B");
    expect(formatArtists([])).toBeNull();
    expect(formatArtists(null)).toBeNull();
    expect(formatArtists([{ name: "  " }])).toBeNull();
  });

  it("formats durations and keeps missing durations absent", () => {
    expect(formatDuration(187)).toBe("3:07");
    expect(formatDuration(3725)).toBe("1:02:05");
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(null)).toBeNull();
    expect(formatDuration(undefined)).toBeNull();
    expect(formatDuration(Number.NaN)).toBeNull();
    expect(formatDuration(-3)).toBeNull();
  });

  it("counts results in words", () => {
    expect(formatResultCount(0)).toBe("No tracks");
    expect(formatResultCount(1)).toBe("1 track");
    expect(formatResultCount(12)).toBe("12 tracks");
  });

  it("humanizes unknown codes without inventing meaning", () => {
    expect(humanize("some_new_flag")).toBe("Some new flag");
    expect(humanize("a:b")).toBe("A b");
  });

  it("has no percentage formatter", async () => {
    const modules = [await import("./text"), await import("./labels")];
    const names = modules.flatMap((m) => Object.keys(m));
    expect(names.filter((n) => /percent|pct|probab/i.test(n))).toEqual([]);
  });
});

describe("labels", () => {
  it("labels evidence, sources, metrics and relationships, with readable fallbacks", () => {
    expect(evidenceLabel("metadata_only")).toBe("Matched on catalog data only");
    expect(evidenceLabel("audio_and_metadata")).toBe("Matched on sound and catalog data");
    expect(evidenceLabel("lyrics_only" as EvidenceStatus)).toBe("Lyrics only");
    expect(retrievalSourceLabel("semantic")).toBe("sound");
    expect(neighborMetricLabel("clap_cosine")).toBe("Nearby in sound");
    expect(neighborMetricLabel("catalog_relationship")).toBe("Related in the catalog");
    expect(neighborMetricLabel("new_metric" as NeighborMetric)).toBe("New metric");
    expect(relationshipLabel("same_artist")).toBe("Same artist");
    expect(relationshipLabel("same_mood" as RelationshipType)).toBe("Same mood");
  });

  it("labels uncertainty flags, including per-constraint ones", () => {
    expect(uncertaintyLabel("no_audio")).toBe("No audio analysis for this track");
    expect(uncertaintyLabel("semantic_unavailable")).toBe("Sound-based matching was unavailable");
    expect(uncertaintyLabel("vocals_unknown")).toBe("Vocals not verified");
    expect(uncertaintyLabel("constraint_unknown:vocals")).toBe("Vocals not verified");
    expect(uncertaintyLabel("constraint_unknown:mood")).toBe("Mood not verified");
    expect(uncertaintyLabel("brand_new_flag")).toBe("Brand new flag");
  });

  it("states hard constraints the way a user would", () => {
    expect(hardConstraintLabel({ attribute: "vocals", operator: "excluded", value: null, range: null })).toBe("No vocals");
    expect(hardConstraintLabel({ attribute: "vocals", operator: "required", value: null, range: null })).toBe("With vocals");
    expect(hardConstraintLabel({ attribute: "instrument", operator: "excluded", value: "drums", range: null })).toBe("No drums");
    expect(hardConstraintLabel({ attribute: "genre", operator: "required", value: "Folk", range: null })).toBe("Folk only");
    expect(hardConstraintLabel({ attribute: "era", operator: "range", value: null, range: [1990, null] })).toBe("Era: 1990 or later");
    expect(hardConstraintLabel({ attribute: "era", operator: "range", value: null, range: [null, 1989] })).toBe("Era: up to 1989");
    expect(hardConstraintLabel({ attribute: "tempo", operator: "range", value: null, range: [100, 120] })).toBe("Tempo: 100 BPM–120 BPM");
    expect(hardConstraintLabel({ attribute: "duration", operator: "range", value: null, range: [null, 180] })).toBe("Duration: up to 3:00");
    expect(attributeLabel("timbre")).toBe("Timbre");
  });

  it("labels constraint checks with their status", () => {
    const check: ConstraintCheck = { attribute: "vocals", operator: "excluded", value: null, status: "unknown" };
    expect(constraintCheckLabel(check)).toBe("No vocals: not verified");
    expect(constraintCheckLabel({ ...check, status: "satisfied" })).toBe("No vocals: met");
  });

  it("keeps an unspecified vocal preference absent", () => {
    expect(vocalPreferenceLabel("unspecified")).toBeNull();
    expect(vocalPreferenceLabel("avoided")).toBe("Fewer vocals");
    expect(vocalPreferenceLabel("excluded")).toBe("No vocals");
  });

  it("maps error codes to human messages and never shows the raw code", () => {
    expect(errorMessage("track_not_found")).toBe("That track isn't in the catalog.");
    expect(errorMessage("network_error")).toMatch(/couldn't be reached/);
    expect(errorMessage("weird_internal_thing")).toBe("Something went wrong. Retry.");
    expect(errorMessage(null)).toBe("Something went wrong. Retry.");
  });
});
