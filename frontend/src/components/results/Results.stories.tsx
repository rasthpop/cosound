// Results panel and rows in every state U02.T03 lists, from the contract fixtures.
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState, type ReactNode } from "react";

import type { SearchResponse } from "@/api/types";
import { fixture } from "@/mocks/fixtures";

import { EmptyState } from "../states/EmptyState";
import { ErrorState } from "../states/ErrorState";
import { NoConfidentMatch } from "../states/NoConfidentMatch";
import { ResultRow } from "./ResultRow";
import { ResultsList, ResultsPanel } from "./ResultsPanel";

const Stage = ({ children }: { children: ReactNode }) => (
  <main className="flex h-dvh items-stretch bg-surface-canvas p-3 text-fg">{children}</main>
);

/** Rows for a plate; a fake playable URL stands in for useMediaUrl(preview_url). */
function Rows({ plate, selected }: { plate: SearchResponse; selected?: string }) {
  const [playing, setPlaying] = useState<string | null>(null);
  return (
    <ResultsList>
      {plate.results.map((r) => (
        <ResultRow
          key={r.track_id}
          result={r}
          playUrl={r.preview_url ? `data:audio/mpeg;base64,` : null}
          playing={playing === r.track_id}
          selected={selected === r.track_id}
          onTrackSelect={() => {}}
          onTrackHover={() => {}}
          onPlay={setPlaying}
        />
      ))}
    </ResultsList>
  );
}

function Plate({ name, stale, selected }: { name: "search_ok" | "search_semantic_unavailable" | "search_constraint_unknown"; stale?: boolean; selected?: string }) {
  const plate = fixture(name);
  return (
    <Stage>
      <ResultsPanel query={plate.interpreted_query.original_query} count={plate.results.length} stale={stale ?? false}>
        <Rows plate={plate} {...(selected ? { selected } : {})} />
      </ResultsPanel>
    </Stage>
  );
}

const meta = { title: "Results", parameters: { layout: "fullscreen" } } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const Ok: Story = { render: () => <Plate name="search_ok" selected="trk_example_2" /> };
export const Stale: Story = { render: () => <Plate name="search_ok" stale /> };
export const DegradedSemantic: Story = { render: () => <Plate name="search_semantic_unavailable" /> };
export const ConstraintNotVerified: Story = { render: () => <Plate name="search_constraint_unknown" /> };

export const WithoutAudioOrCoordinates: Story = {
  name: "Track without audio / without coordinates",
  render: () => {
    const plate = fixture("search_ok");
    return (
      <Stage>
        <ResultsPanel query={plate.interpreted_query.original_query} count={1}>
          <Rows plate={{ ...plate, results: plate.results.filter((r) => r.preview_url === null) }} />
        </ResultsPanel>
      </Stage>
    );
  },
};

export const Empty: Story = {
  render: () => {
    const plate = fixture("search_empty");
    return (
      <Stage>
        <ResultsPanel query={plate.interpreted_query.original_query} count={0}>
          <EmptyState query={plate.interpreted_query.original_query} onEditQuery={() => {}} />
        </ResultsPanel>
      </Stage>
    );
  },
};

export const NoConfidentMatchBody: Story = {
  name: "No confident match",
  render: () => {
    const plate = fixture("search_no_confident_match");
    return (
      <Stage>
        <ResultsPanel query={plate.interpreted_query.original_query} count={plate.results.length}>
          <NoConfidentMatch reasons={plate.no_match_reasons} onEditQuery={() => {}} />
        </ResultsPanel>
      </Stage>
    );
  },
};

export const ErrorBody: Story = {
  name: "Error",
  render: () => (
    <Stage>
      <ResultsPanel query="something chill with a flute" count={null}>
        <ErrorState error={fixture("error_internal").error} onRetry={() => {}} />
      </ResultsPanel>
    </Stage>
  ),
};

const sheet = (snap: 0 | 1 | 2): Story => ({
  globals: { viewport: { value: "mobile2", isRotated: false } },
  render: () => {
    const plate = fixture("search_ok");
    return (
      <Stage>
        <ResultsPanel variant="sheet" initialSnap={snap} query={plate.interpreted_query.original_query} count={plate.results.length}>
          <Rows plate={plate} />
        </ResultsPanel>
      </Stage>
    );
  },
});

export const SheetPeek = { ...sheet(0), name: "Bottom sheet: peek" };
export const SheetHalf = { ...sheet(1), name: "Bottom sheet: half" };
export const SheetFull = { ...sheet(2), name: "Bottom sheet: full" };

export const LightTheme: Story = {
  globals: { theme: "light" },
  render: () => <Plate name="search_ok" selected="trk_example_1" />,
};
