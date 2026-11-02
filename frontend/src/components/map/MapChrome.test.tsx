import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fixture } from "@/mocks/fixtures";
import { ThemeProvider } from "@/theme/ThemeProvider";

import { GenreLegend } from "./GenreLegend";
import { MAP_CAPTION, MapCaption } from "./MapCaption";
import { MapControls } from "./MapControls";
import { MapFallback } from "./MapFallback";
import { MapPointList } from "./MapPointList";

afterEach(cleanup);

const wrap = (ui: ReactNode) => render(<ThemeProvider storageKey={null}>{ui}</ThemeProvider>);
const GENRES = fixture("map_meta").genres;

function Legend({ onGenreFilter }: { onGenreFilter: (g: string | null) => void }) {
  const [active, setActive] = useState<string | null>(null);
  return (
    <GenreLegend
      genres={[...GENRES, { genre: null, count: 2 }]}
      activeGenre={active}
      onGenreFilter={(g) => {
        setActive(g);
        onGenreFilter(g);
      }}
    />
  );
}

describe("GenreLegend", () => {
  it("emits the genre, then null on the second click", async () => {
    const onGenreFilter = vi.fn();
    wrap(<Legend onGenreFilter={onGenreFilter} />);
    const folk = screen.getByRole("button", { name: /Folk/ });
    await userEvent.click(folk);
    expect(onGenreFilter).toHaveBeenLastCalledWith("Folk");
    expect(folk).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(folk);
    expect(onGenreFilter).toHaveBeenLastCalledWith(null);
  });

  it("shows counts, labels points without a genre neutrally and does not make them a filter", () => {
    wrap(<Legend onGenreFilter={() => {}} />);
    expect(screen.getByRole("button", { name: /Folk\s*3/ })).toBeInTheDocument();
    const none = screen.getByText("No genre");
    expect(none.closest("button")).toBeNull();
  });

  it("is hidden when the API sent no genre summary", () => {
    const { container } = wrap(<GenreLegend genres={[]} activeGenre={null} onGenreFilter={() => {}} />);
    expect(container.querySelector("section")).toBeNull();
    cleanup();
    expect(wrap(<GenreLegend genres={undefined} activeGenre={null} onGenreFilter={() => {}} />).container.querySelector("section")).toBeNull();
  });
});

describe("MapControls", () => {
  it("emits each control", async () => {
    const handlers = { onZoomIn: vi.fn(), onZoomOut: vi.fn(), onReset: vi.fn(), onLegendToggle: vi.fn(), onListToggle: vi.fn(), onAudioOnlyChange: vi.fn() };
    wrap(<MapControls legendOpen={false} listOpen={false} audioOnly={false} {...handlers} />);
    await userEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    await userEvent.click(screen.getByRole("button", { name: "Zoom out" }));
    await userEvent.click(screen.getByRole("button", { name: "Reset view" }));
    await userEvent.click(screen.getByRole("button", { name: "Genre legend" }));
    await userEvent.click(screen.getByRole("button", { name: "List of map tracks" }));
    await userEvent.click(screen.getByRole("button", { name: "Only tracks with audio" }));
    expect(handlers.onZoomIn).toHaveBeenCalledOnce();
    expect(handlers.onZoomOut).toHaveBeenCalledOnce();
    expect(handlers.onReset).toHaveBeenCalledOnce();
    expect(handlers.onLegendToggle).toHaveBeenCalledWith(true);
    expect(handlers.onListToggle).toHaveBeenCalledWith(true);
    expect(handlers.onAudioOnlyChange).toHaveBeenCalledWith(true);
  });
});

describe("caption, list and fallback", () => {
  it("never claims distance equals similarity", () => {
    wrap(<MapCaption />);
    expect(screen.getByText(MAP_CAPTION)).toBeInTheDocument();
    expect(MAP_CAPTION).toMatch(/suggestive, not exact/);
  });

  it("lists the same points a page at a time and selects by keyboard", async () => {
    const points = Array.from({ length: 5 }, (_, i) => ({ track_id: `t${i}`, title: `Track ${i}`, artist: null, genre: "Folk" }));
    const onTrackSelect = vi.fn();
    wrap(<MapPointList points={points} pageSize={2} highlightedTrackIds={new Set(["t1"])} onTrackSelect={onTrackSelect} />);
    expect(screen.getAllByRole("button", { name: /^Track/ })).toHaveLength(2);
    expect(screen.getByText("· in results")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show 2 more" }));
    expect(screen.getAllByRole("button", { name: /^Track/ })).toHaveLength(4);
    screen.getByRole("button", { name: /Track 3/ }).focus();
    await userEvent.keyboard("{Enter}");
    expect(onTrackSelect).toHaveBeenCalledWith("t3");
  });

  it("explains an unavailable map and a WebGL failure", () => {
    wrap(<MapFallback reason="unavailable" />);
    expect(screen.getByRole("status")).toHaveTextContent("Map is unavailable — search still works.");
    cleanup();
    wrap(<MapFallback reason="webgl"><p>list</p></MapFallback>);
    expect(screen.getByRole("status")).toHaveTextContent("couldn't draw the map");
    expect(screen.getByText("list")).toBeInTheDocument();
  });
});
