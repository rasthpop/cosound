// Views for the U00 contract additions (G1-G3), from the regenerated fixtures: match bands on
// result rows, per-signal score bands in the drawer, and structured "what changed" entries.
import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ReactNode } from "react";

import { fixture } from "@/mocks/fixtures";

import { ChangeStrip } from "../feedback/ChangeStrip";
import { ScoreBands } from "../track/ScoreBands";
import { MatchBand } from "./MatchBand";
import { ResultRow } from "./ResultRow";
import { ResultsList, ResultsPanel } from "./ResultsPanel";

const plate = fixture("search_ok");
const refined = fixture("feedback_refined");

const Stage = ({ children }: { children: ReactNode }) => (
  <main className="flex min-h-dvh flex-col items-start gap-2 bg-surface-canvas p-3 text-fg">{children}</main>
);

const meta = { title: "Contract additions" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const MatchBands: Story = {
  render: () => (
    <Stage>
      <div className="flex gap-2">
        <MatchBand band="strong" />
        <MatchBand band="partial" />
      </div>
      <ResultsPanel query={plate.interpreted_query.original_query} count={plate.results.length}>
        <ResultsList>
          {plate.results.map((r) => (
            <ResultRow key={r.track_id} result={r} playUrl={null} onTrackSelect={() => {}} />
          ))}
        </ResultsList>
      </ResultsPanel>
    </Stage>
  ),
};

export const ScoreBandsCollapsed: Story = {
  render: () => (
    <Stage>
      <ScoreBands bands={plate.results[0]!.score_bands} />
    </Stage>
  ),
};

export const ScoreBandsOpen: Story = {
  render: () => (
    <Stage>
      <ScoreBands bands={plate.results[2]!.score_bands} />
    </Stage>
  ),
  play: async ({ canvasElement }) => {
    canvasElement.querySelector("details")?.setAttribute("open", "");
  },
};

export const StructuredChanges: Story = {
  render: () => (
    <Stage>
      <div className="w-47.5">
        <ChangeStrip
          changeSummary={refined.change_summary}
          changes={refined.changes}
          originalQuery={plate.interpreted_query.original_query}
          onDismiss={() => {}}
        />
      </div>
    </Stage>
  ),
};

export const LightTheme: Story = {
  globals: { theme: "light" },
  render: () => (
    <Stage>
      <MatchBand band="strong" />
      <MatchBand band="partial" />
      <ScoreBands bands={plate.results[1]!.score_bands} />
      <div className="w-47.5">
        <ChangeStrip changeSummary={refined.change_summary} changes={refined.changes} originalQuery="x" onDismiss={() => {}} />
      </div>
    </Stage>
  ),
};
