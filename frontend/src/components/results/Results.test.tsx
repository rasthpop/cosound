import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TrackResult } from "@/api/types";
import { fixture } from "@/mocks/fixtures";

import { EvidenceNote } from "./EvidenceNote";
import { ResultRow } from "./ResultRow";
import { ResultsList, ResultsPanel } from "./ResultsPanel";

afterEach(cleanup);

const plate = fixture("search_ok");

function renderRows(results: TrackResult[], props: Partial<Parameters<typeof ResultRow>[0]> = {}) {
  return render(
    <ResultsPanel query={plate.interpreted_query.original_query} count={results.length}>
      <ResultsList>
        {results.map((r) => (
          <ResultRow key={r.track_id} result={r} playUrl={r.preview_url} onTrackSelect={() => {}} {...props} />
        ))}
      </ResultsList>
    </ResultsPanel>,
  );
}

describe("ResultsPanel and ResultRow", () => {
  it("renders rows in the order given, never re-sorted", () => {
    const shuffled = [plate.results[2], plate.results[0], plate.results[1]] as TrackResult[];
    renderRows(shuffled);
    const titles = within(screen.getByRole("list", { name: "Ranked results" }))
      .getAllByRole("button", { name: /^Example Track/ })
      .map((b) => b.textContent);
    expect(titles).toEqual(["Example Track 3", "Example Track 1", "Example Track 2"]);
  });

  it("shows no percentages or raw scores", () => {
    renderRows(plate.results);
    expect(document.body.textContent).not.toMatch(/%/);
    expect(document.body.textContent).not.toMatch(/0\.\d{2}/);
  });

  it("echoes the query and counts in words", () => {
    renderRows(plate.results);
    expect(screen.getByRole("heading", { name: "3 tracks" })).toBeInTheDocument();
    expect(screen.getByText(`for “${plate.interpreted_query.original_query}”`)).toBeInTheDocument();
  });

  it("a null description renders nothing and reasons are shown as given", () => {
    const [first] = plate.results as [TrackResult];
    renderRows([{ ...first, description: null }]);
    expect(screen.queryByText(first.description ?? "")).toBeNull();
    for (const reason of first.match_reasons) expect(screen.getByText(reason)).toBeInTheDocument();
  });

  it("links to FMA only with a source_url, and plays only with a playable URL", () => {
    const [first, , third] = plate.results as [TrackResult, TrackResult, TrackResult];
    renderRows([first, third], { onPlay: () => {} });
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.getAllByRole("button", { name: /^Play / })).toHaveLength(1); // the one with preview_url
    cleanup();
    renderRows([{ ...first, source_url: "https://freemusicarchive.org/t/1" }]);
    const link = screen.getByRole("link", { name: "Open Example Track 1 on FMA" });
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("marks tracks without coordinates and explains missing audio", () => {
    renderRows([plate.results[2] as TrackResult]);
    expect(screen.getByText("Not on map")).toBeInTheDocument();
    // the evidence status and the no_audio flag say the same thing once, not twice
    expect(screen.getByText("No audio analysis for this track")).toBeInTheDocument();
    expect(screen.queryByText(/·/)).toBeNull();
  });

  it("emits select, hover and play events with the track id", async () => {
    const onTrackSelect = vi.fn();
    const onTrackHover = vi.fn();
    const onPlay = vi.fn();
    renderRows([plate.results[0] as TrackResult], { onTrackSelect, onTrackHover, onPlay });
    await userEvent.click(screen.getByRole("button", { name: "Example Track 1" }));
    expect(onTrackSelect).toHaveBeenCalledWith("trk_example_1");
    expect(onTrackHover).toHaveBeenCalledWith("trk_example_1");
    await userEvent.click(screen.getByRole("button", { name: "Play Example Track 1" }));
    expect(onPlay).toHaveBeenCalledWith("trk_example_1");
  });

  it("collapses and expands", async () => {
    renderRows(plate.results);
    await userEvent.click(screen.getByRole("button", { name: "Hide results" }));
    expect(screen.queryByRole("list", { name: "Ranked results" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Show results" }));
    expect(screen.getByRole("list", { name: "Ranked results" })).toBeInTheDocument();
  });
});

describe("EvidenceNote", () => {
  it("is silent for a full-evidence match and lists flags otherwise", () => {
    const { container } = render(<EvidenceNote evidence_status="audio_and_metadata" uncertainty_flags={[]} retrieval_sources={["semantic"]} />);
    expect(container).toBeEmptyDOMElement();
    render(<EvidenceNote evidence_status="audio_and_metadata" uncertainty_flags={["semantic_unavailable"]} retrieval_sources={["metadata"]} />);
    expect(screen.getByText(/Sound-based matching was unavailable/)).toBeInTheDocument();
  });
});
