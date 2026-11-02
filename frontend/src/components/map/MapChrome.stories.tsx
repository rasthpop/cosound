// Map controls, legend, caption and fallbacks (U03.T04), from the contract fixtures and the mock
// point generator.
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState, type ReactNode } from "react";

import { fixture } from "@/mocks/fixtures";
import { generateMapPoints } from "@/mocks/generateMapPoints";

import { GenreLegend } from "./GenreLegend";
import { MapCaption } from "./MapCaption";
import { MapControls } from "./MapControls";
import { MapFallback } from "./MapFallback";
import { MapPointList } from "./MapPointList";

const POINTS = generateMapPoints(300);
const genresOf = (points: typeof POINTS) => {
  const counts = new Map<string | null, number>();
  for (const p of points) counts.set(p.genre, (counts.get(p.genre) ?? 0) + 1);
  return [...counts].map(([genre, count]) => ({ genre, count })).sort((a, b) => b.count - a.count);
};
const GENRES = genresOf(POINTS);

const Stage = ({ children }: { children: ReactNode }) => (
  <main className="flex h-dvh flex-col items-start justify-end gap-1 bg-surface-canvas p-3 text-fg">{children}</main>
);

function Chrome({ initialGenre = null }: { initialGenre?: string | null }) {
  const [legend, setLegend] = useState(true);
  const [list, setList] = useState(false);
  const [audio, setAudio] = useState(false);
  const [genre, setGenre] = useState<string | null>(initialGenre);
  return (
    <Stage>
      {list && <MapPointList points={POINTS} onTrackSelect={() => {}} />}
      {legend && <GenreLegend genres={GENRES} activeGenre={genre} onGenreFilter={setGenre} />}
      <MapControls
        onZoomIn={() => {}}
        onZoomOut={() => {}}
        onReset={() => {}}
        legendOpen={legend}
        onLegendToggle={setLegend}
        listOpen={list}
        onListToggle={setList}
        audioOnly={audio}
        onAudioOnlyChange={setAudio}
      />
      <MapCaption />
    </Stage>
  );
}

const meta = { title: "Map/Controls & fallbacks", parameters: { layout: "fullscreen" } } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const ControlsAndLegend: Story = { render: () => <Chrome /> };
export const LegendFiltered: Story = { name: "Legend with a genre filter", render: () => <Chrome initialGenre={GENRES[0]?.genre ?? null} /> };
export const LegendFromFixture: Story = {
  name: "Legend from map_meta fixture",
  render: () => (
    <Stage>
      <GenreLegend genres={fixture("map_meta").genres} activeGenre={null} onGenreFilter={() => {}} />
    </Stage>
  ),
};
export const ListAlternative: Story = {
  render: () => (
    <Stage>
      <MapPointList points={POINTS} highlightedTrackIds={new Set([POINTS[2]!.track_id])} selectedTrackIds={new Set([POINTS[2]!.track_id])} onTrackSelect={() => {}} />
    </Stage>
  ),
};
export const MapDown: Story = {
  name: "Map unavailable",
  render: () => (
    <main className="h-dvh">
      <MapFallback reason="unavailable" />
    </main>
  ),
};
export const WebGLFailure: Story = {
  render: () => (
    <main className="h-dvh">
      <MapFallback reason="webgl">
        <MapPointList points={POINTS} onTrackSelect={() => {}} />
      </MapFallback>
    </main>
  ),
};
export const LightTheme: Story = { globals: { theme: "light" }, render: () => <Chrome initialGenre={GENRES[1]?.genre ?? null} /> };
