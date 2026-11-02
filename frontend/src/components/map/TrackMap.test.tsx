import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeProvider } from "@/theme/ThemeProvider";

import { TrackMap, type TrackMapPoint, type TrackMapProps } from "./TrackMap";

// deck.gl needs WebGL, which jsdom lacks: the DeckGL component is replaced by a stub that records
// its props. Layers are the real ScatterplotLayer objects, so their props are what deck.gl gets.
type DeckProps = Record<string, unknown> & {
  layers: { props: Record<string, unknown> }[];
  viewState: { target: number[]; zoom: number; transitionDuration: number };
};
const deck: { props: DeckProps | null } = { props: null };
vi.mock("@deck.gl/react", () => ({
  default: (props: DeckProps) => {
    deck.props = props;
    return <div data-testid="deck" />;
  },
}));

const POINTS: TrackMapPoint[] = [
  { track_id: "trk_a", x: -1, y: 0, genre: "Folk", title: "A", artist: "X" },
  { track_id: "trk_b", x: 1, y: 1, genre: "Rock", title: "B", artist: "Y" },
  { track_id: "trk_c", x: 0, y: -1, genre: null, title: "C", artist: null },
];
const GENRES = [
  { genre: "Folk", count: 1 },
  { genre: "Rock", count: 1 },
  { genre: null, count: 1 },
];

const layer = () => deck.props!.layers[0]!.props;
const triggers = () => layer().updateTriggers as Record<string, string>;

function renderMap(props: Partial<TrackMapProps> = {}) {
  const all: TrackMapProps = { points: POINTS, genres: GENRES, onTrackSelect: () => {}, ariaLabel: "Track map", ...props };
  const ui = (p: TrackMapProps) => (
    <ThemeProvider storageKey={null}>
      <TrackMap {...p} />
    </ThemeProvider>
  );
  const r = render(ui(all));
  return { ...r, rerenderMap: (next: Partial<TrackMapProps>) => r.rerender(ui({ ...all, ...next })) };
}

beforeEach(() => {
  deck.props = null;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    width: 800, height: 600, top: 0, left: 0, right: 800, bottom: 600, x: 0, y: 0, toJSON: () => ({}),
  } as DOMRect); // fmt: skip
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("TrackMap", () => {
  it("draws the points in an orthographic view with one stable scatterplot layer", () => {
    renderMap();
    expect(screen.getByTestId("deck")).toBeInTheDocument();
    expect(deck.props!.layers).toHaveLength(1);
    expect(layer().id).toBe("tracks");
    expect(layer().data).toBe(POINTS);
    expect(layer().radiusUnits).toBe("pixels");
  });

  it("a picked click emits onTrackSelect with the track id; a miss emits nothing", () => {
    const onTrackSelect = vi.fn();
    renderMap({ onTrackSelect });
    const onClick = deck.props!.onClick as (info: { object?: TrackMapPoint }) => void;
    act(() => onClick({ object: POINTS[1]! }));
    expect(onTrackSelect).toHaveBeenCalledWith("trk_b");
    act(() => onClick({}));
    expect(onTrackSelect).toHaveBeenCalledTimes(1);
  });

  it("update triggers change with selection and highlight, not with Set identity", () => {
    const { rerenderMap } = renderMap({ selectedTrackIds: new Set(["trk_a"]) });
    const before = triggers();
    rerenderMap({ selectedTrackIds: new Set(["trk_a"]) });
    expect(triggers()).toEqual(before);
    rerenderMap({ selectedTrackIds: new Set(["trk_b"]) });
    expect(triggers().getRadius).not.toBe(before.getRadius);
    const selected = triggers();
    rerenderMap({ selectedTrackIds: new Set(["trk_b"]), highlightedTrackIds: new Set(["trk_c"]), dimUnhighlighted: true });
    expect(triggers().getFillColor).not.toBe(selected.getFillColor);
  });

  it("reports WebGL errors to the container", () => {
    const onWebGLError = vi.fn();
    renderMap({ onWebGLError });
    const error = new Error("WebGL2 is not available");
    act(() => (deck.props!.onError as (e: Error) => void)(error));
    expect(onWebGLError).toHaveBeenCalledWith(error);
  });

  it("hover emits the track id, then null, and shows the tooltip from MapPoint fields", () => {
    const onTrackHover = vi.fn();
    renderMap({ onTrackHover, renderTooltip: (p) => <span>tip {p.title}</span> });
    const onHover = deck.props!.onHover as (info: { object?: TrackMapPoint; x: number; y: number }) => void;
    act(() => onHover({ object: POINTS[0]!, x: 10, y: 20 }));
    expect(onTrackHover).toHaveBeenLastCalledWith("trk_a");
    expect(screen.getByText("tip A")).toBeInTheDocument();
    act(() => onHover({ x: 0, y: 0 }));
    expect(onTrackHover).toHaveBeenLastCalledWith(null);
    expect(screen.queryByText("tip A")).toBeNull();
  });

  it("summarises the map for screen readers and resets on the 0 key", async () => {
    const onResetRequest = vi.fn();
    renderMap({ onResetRequest, highlightedTrackIds: new Set(["trk_a", "trk_b"]) });
    expect(screen.getByText(/Map of 3 tracks; 2 results highlighted/)).toBeInTheDocument();
    screen.getByRole("region", { name: "Track map" }).focus();
    await userEvent.keyboard("0");
    expect(onResetRequest).toHaveBeenCalledOnce();
  });

  it("fits the camera to a requested subset, once per request key", () => {
    const { rerenderMap } = renderMap();
    const all = deck.props!.viewState;
    expect(all.target.slice(0, 2)).toEqual([0, 0]);
    const fitTo: ComponentProps<typeof TrackMap>["fitTo"] = { bounds: { min_x: 1, max_x: 1, min_y: 1, max_y: 1 }, key: "results-1" };
    rerenderMap({ fitTo });
    expect(deck.props!.viewState.target.slice(0, 2)).toEqual([1, 1]);
    expect(deck.props!.viewState.transitionDuration).toBe(600);
  });
});
