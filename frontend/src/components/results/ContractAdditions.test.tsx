import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { ChangeEntry, TrackResult } from "@/api/types";
import { fixture } from "@/mocks/fixtures";

import { ChangeStrip } from "../feedback/ChangeStrip";
import { changeLabel } from "../format/labels";
import { ScoreBands } from "../track/ScoreBands";
import { MatchBand } from "./MatchBand";
import { ResultRow } from "./ResultRow";

afterEach(cleanup);

const NUMBERS = /\d|%/;
const entry = (kind: ChangeEntry["kind"], fields: Partial<ChangeEntry> = {}): ChangeEntry => ({
  kind,
  track_id: null,
  title: null,
  attribute: null,
  value: null,
  operator: null,
  ...fields,
});

describe("MatchBand", () => {
  it("names strong and partial bands, shows nothing for weak or missing, never a number", () => {
    const { rerender, container } = render(<MatchBand band="strong" />);
    expect(container).toHaveTextContent("Strong match");
    rerender(<MatchBand band="partial" />);
    expect(container).toHaveTextContent("Partial match");
    expect(container.textContent).not.toMatch(NUMBERS);
    rerender(<MatchBand band="weak" />);
    expect(container).toBeEmptyDOMElement();
    rerender(<MatchBand band={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("is part of every result row", () => {
    const [first] = fixture("search_ok").results as [TrackResult];
    render(<ResultRow result={first} playUrl={null} onTrackSelect={() => {}} />);
    expect(screen.getByText("Strong match")).toBeInTheDocument();
  });
});

describe("ScoreBands", () => {
  it("is collapsed by default and shows null bands as 'not available', never 0 or a number", async () => {
    const { container } = render(<ScoreBands bands={{ semantic: "strong", metadata: null, relationship: null }} />);
    const details = container.querySelector("details");
    expect(details).not.toHaveAttribute("open");
    await userEvent.click(screen.getByText("How it matched"));
    expect(details).toHaveAttribute("open");
    expect(screen.getByText("Strong")).toBeInTheDocument();
    expect(screen.getAllByText("not available")).toHaveLength(2);
    expect(container.textContent).not.toMatch(NUMBERS);
  });
});

describe("ChangeStrip with structured changes", () => {
  it("renders feedback_refined's structured changes with track titles", () => {
    const refined = fixture("feedback_refined");
    render(<ChangeStrip changeSummary={refined.change_summary} changes={refined.changes} originalQuery="q" onDismiss={() => {}} />);
    for (const change of refined.changes) expect(screen.getByText(changeLabel(change))).toBeInTheDocument();
    const excluded = refined.changes.find((c) => c.kind === "excluded");
    expect(screen.getByText(`Removed “${excluded?.title}”`)).toBeInTheDocument();
    for (const c of refined.changes) if (c.track_id) expect(document.body.textContent).not.toContain(c.track_id);
  });

  it("falls back to change_summary strings when there are no structured entries", () => {
    render(<ChangeStrip changeSummary={["removed a track"]} changes={[]} originalQuery="q" onDismiss={() => {}} />);
    expect(screen.getByText("removed a track")).toBeInTheDocument();
  });

  it("an entry with title: null never shows the raw track id", () => {
    const change = entry("excluded", { track_id: "trk_secret_42", title: null });
    render(<ChangeStrip changeSummary={["removed trk_secret_42"]} changes={[change]} originalQuery="q" onDismiss={() => {}} />);
    expect(screen.getByText("Removed a track")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("trk_secret_42");
  });

  it("labels every change kind without inventing data", () => {
    expect(changeLabel(entry("reference_added", { track_id: "t", title: "Night Train" }))).toBe("More like “Night Train”");
    expect(changeLabel(entry("negative_reference_added", { track_id: "t" }))).toBe("Less like a track");
    expect(changeLabel(entry("excluded", { track_id: "t", title: "Bus", attribute: "instrument", value: "flute" }))).toBe("Removed “Bus” (you marked flute as wrong)");
    expect(changeLabel(entry("preference_added", { attribute: "genre", value: "electronic" }))).toBe("Added electronic");
    expect(changeLabel(entry("preference_raised", { attribute: "mood", value: "chill" }))).toBe("More chill");
    expect(changeLabel(entry("preference_lowered", { attribute: "vocals", value: "vocals" }))).toBe("Fewer vocals");
    expect(changeLabel(entry("preference_removed", { attribute: "mood", value: "chill" }))).toBe("Dropped chill");
    expect(changeLabel(entry("negative_added", { value: "acoustic" }))).toBe("Avoiding acoustic");
    expect(changeLabel(entry("negative_removed", { value: "acoustic" }))).toBe("No longer avoiding acoustic");
    expect(changeLabel(entry("constraint_added", { attribute: "vocals", operator: "excluded" }))).toBe("Now required: No vocals");
    expect(changeLabel(entry("rejected", { attribute: "zxqv" }))).toBe("That feedback was not applied");
    expect(changeLabel(entry("needs_clarification", { value: "Vocals or not?" }))).toBe("Needs clarification: Vocals or not?");
  });
});
