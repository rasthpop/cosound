// Feedback controls and the change strip, from the contract fixtures.
import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ReactNode } from "react";

import { fixture } from "@/mocks/fixtures";

import { errorMessage } from "../format/labels";
import { ResultRow } from "../results/ResultRow";
import { ResultsList, ResultsPanel } from "../results/ResultsPanel";
import { ChangeStrip } from "./ChangeStrip";
import { FeedbackActions, type FeedbackActionsProps } from "./FeedbackActions";

const plate = fixture("search_ok");
const refined = fixture("feedback_refined");
const rejected = fixture("feedback_rejected");
const instruments = plate.interpreted_query.instrument_preferences.map((p) => p.value);

const Stage = ({ children }: { children: ReactNode }) => (
  <main className="flex min-h-dvh flex-col items-start gap-2 bg-surface-canvas p-3 text-fg">{children}</main>
);

const actions = (props: Partial<FeedbackActionsProps> = {}) => (
  <FeedbackActions trackId="trk_example_1" title="Example Track 1" instruments={instruments} layout="labels" onFeedback={() => {}} {...props} />
);

const meta = { title: "Feedback" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const Idle: Story = { render: () => <Stage>{actions()}</Stage> };
export const Pending: Story = { render: () => <Stage>{actions({ status: "pending", lastEvent: "NOT_RELEVANT" })}</Stage> };
export const Applied: Story = { render: () => <Stage>{actions({ status: "applied", lastEvent: "MORE_LIKE_THIS" })}</Stage> };
export const Rejected: Story = {
  render: () => <Stage>{actions({ status: "rejected", lastEvent: "LESS_LIKE_THIS", message: rejected.reason })}</Stage>,
};
export const Error: Story = {
  render: () => (
    <Stage>{actions({ status: "error", lastEvent: "NOT_RELEVANT", message: errorMessage(fixture("error_track_not_in_results").error.code) })}</Stage>
  ),
};
export const NoInstruments: Story = { name: "No instruments in the query (no picker)", render: () => <Stage>{actions({ instruments: [] })}</Stage> };

export const RefinedPlateWithChangeStrip: Story = {
  name: "Refined plate with change strip",
  render: () => {
    const after = refined.refreshed ?? plate;
    return (
      <Stage>
        <ResultsPanel
          query={after.interpreted_query.original_query}
          count={after.results.length}
          changeStrip={<ChangeStrip changeSummary={refined.change_summary} originalQuery={after.interpreted_query.original_query} onDismiss={() => {}} />}
        >
          <ResultsList>
            {after.results.map((r) => (
              <ResultRow
                key={r.track_id}
                result={r}
                playUrl={null}
                onTrackSelect={() => {}}
                actions={<FeedbackActions trackId={r.track_id} title={r.title} instruments={instruments} onFeedback={() => {}} />}
              />
            ))}
          </ResultsList>
        </ResultsPanel>
      </Stage>
    );
  },
};

export const LightTheme: Story = {
  globals: { theme: "light" },
  render: () => (
    <Stage>
      {actions({ status: "rejected", lastEvent: "LESS_LIKE_THIS", message: rejected.reason })}
      <ChangeStrip changeSummary={refined.change_summary} originalQuery={plate.interpreted_query.original_query} onDismiss={() => {}} />
    </Stage>
  ),
};

export const RefinementNotApplied: Story = {
  name: "Refinement not applied",
  render: () => (
    <Stage>
      <ChangeStrip
        changeSummary={rejected.change_summary}
        changes={rejected.changes}
        status="rejected"
        message={rejected.reason}
        originalQuery={plate.interpreted_query.original_query}
        onDismiss={() => {}}
      />
    </Stage>
  ),
};
