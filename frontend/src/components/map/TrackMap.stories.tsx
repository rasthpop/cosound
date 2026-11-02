// The track map in every state U03.T03 lists. Points come from the mock generator (the same one
// `?mapPoints=N` uses), so stories show realistic densities without a backend.
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState, type ReactNode } from "react";
import { expect, waitFor } from "storybook/test";

import type { MapPoint } from "@/api/types";
import { generateMapPoints } from "@/mocks/generateMapPoints";
import { ThemeProvider } from "@/theme/ThemeProvider";

import { MapTooltip } from "./MapTooltip";
import { TrackMap, type TrackMapProps } from "./TrackMap";

/** `MapMeta.genres` for a point set (the API computes this server-side). */
function genresOf(points: readonly MapPoint[]) {
  const counts = new Map<string | null, number>();
  for (const p of points) counts.set(p.genre, (counts.get(p.genre) ?? 0) + 1);
  return [...counts].map(([genre, count]) => ({ genre, count })).sort((a, b) => b.count - a.count);
}

const FIELD = generateMapPoints(2000);
const DENSE = generateMapPoints(10000);
const RESULTS = new Set(FIELD.filter((_, i) => i % 211 === 0).map((p) => p.track_id));
const SELECTED = FIELD.find((p) => RESULTS.has(p.track_id))?.track_id ?? "";

function MapStage(props: Partial<TrackMapProps> & { points?: MapPoint[] }) {
  const points = props.points ?? FIELD;
  const [error, setError] = useState<string | null>(null);
  return (
    <main className="relative h-dvh w-full bg-surface-canvas text-fg">
      <TrackMap
        points={points}
        genres={genresOf(points)}
        onTrackSelect={() => {}}
        onWebGLError={(e) => setError(e.message)}
        renderTooltip={(p) => <MapTooltip point={p} />}
        ariaLabel="Track map"
        {...props}
      />
      {error && (
        <p role="alert" className="absolute top-1 left-1 text-meta">
          WebGL error: {error}
        </p>
      )}
    </main>
  );
}

const rendersCanvas = async ({ canvasElement }: { canvasElement: HTMLElement }) => {
  await waitFor(() => expect(canvasElement.querySelector("canvas")).not.toBeNull(), { timeout: 5000 });
  await expect(canvasElement.querySelector('[role="alert"]')).toBeNull();
};

const meta = { title: "Map/TrackMap", parameters: { layout: "fullscreen" } } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const IdleField: Story = { render: () => <MapStage />, play: rendersCanvas };

export const Hover: Story = {
  name: "Hover (tooltip)",
  render: () => {
    const hovered = FIELD[0]!;
    return (
      <>
        <MapStage hoveredTrackId={hovered.track_id} />
        <div className="absolute top-2 left-2">
          <MapTooltip point={hovered} />
        </div>
      </>
    );
  },
};

export const OneSelected: Story = {
  render: () => <MapStage selectedTrackIds={new Set([SELECTED])} />,
  play: rendersCanvas,
};

export const ResultsHighlighted: Story = {
  name: "Results highlighted, others dimmed",
  render: () => <MapStage highlightedTrackIds={RESULTS} dimUnhighlighted selectedTrackIds={new Set([SELECTED])} />,
  play: rendersCanvas,
};

const Reduced = ({ children }: { children: ReactNode }) => (
  <ThemeProvider storageKey={null} defaultPreference="dark" reducedMotion>
    {children}
  </ThemeProvider>
);

export const ReducedMotion: Story = {
  name: "Reduced motion (no pulse, instant camera)",
  render: () => (
    <Reduced>
      <MapStage highlightedTrackIds={RESULTS} dimUnhighlighted selectedTrackIds={new Set([SELECTED])} />
    </Reduced>
  ),
  play: rendersCanvas,
};

export const TenThousandPoints: Story = {
  name: "10k points",
  render: () => <MapStage points={DENSE} />,
  play: rendersCanvas,
};

export const LightTheme: Story = {
  globals: { theme: "light" },
  render: () => <MapStage highlightedTrackIds={RESULTS} dimUnhighlighted selectedTrackIds={new Set([SELECTED])} />,
  play: rendersCanvas,
};

export const TouchCard: Story = {
  name: "Touch: compact card",
  render: () => (
    <main className="flex min-h-dvh items-end bg-surface-canvas p-2 text-fg">
      <MapTooltip point={FIELD[1]!} variant="card" />
    </main>
  ),
};
