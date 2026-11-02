// The map container inside the Discover screen, against the MSW mocks. deck.gl needs WebGL, which
// jsdom lacks, so DeckGL is a stub that records its props (as in TrackMap.test.tsx); everything
// else — hooks, containers, views, the real ScatterplotLayer — is real.
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { Profiler } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MapPoint } from "@/api/types";
import { fixture } from "@/mocks/fixtures";
import { handlersFor } from "@/mocks/handlers";
import type { Scenario } from "@/mocks/scenarios";
import { server } from "@/mocks/server";
import { ThemeProvider } from "@/theme/ThemeProvider";

import { DiscoverPage } from "./DiscoverPage";
import { locate, pointBounds, resultsOnMap, withGenre } from "./selection";

type DeckProps = {
  layers: { id: string; props: Record<string, unknown> }[];
  viewState: { target: number[]; zoom: number };
  onClick: (info: { object: MapPoint | null }) => void;
  onHover: (info: { object: MapPoint | null; x: number; y: number }) => void;
  onError: (error: Error) => void;
};
const deck: { props: DeckProps | null } = { props: null };
vi.mock("@deck.gl/react", () => ({
  default: (props: DeckProps) => {
    deck.props = props;
    return <div data-testid="deck" />;
  },
}));

const POINTS = [...fixture("map_points_page1").points, ...fixture("map_points_page2").points];
const point = (id: string) => POINTS.find((p) => p.track_id === id)!;
const RESULTS = fixture("search_ok").results;

beforeEach(() => {
  deck.props = null;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    width: 800, height: 600, top: 0, left: 0, right: 800, bottom: 600, x: 0, y: 0, toJSON: () => ({}),
  } as DOMRect); // fmt: skip
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

/** Request bodies (or query strings) the mock received for `path`. */
function record(path: string) {
  const seen: { url: string; body: unknown }[] = [];
  server.events.on("request:start", async ({ request }) => {
    const url = new URL(request.url);
    if (url.pathname.endsWith(path)) seen.push({ url: request.url, body: request.method === "POST" ? await request.clone().json() : null });
  });
  return seen;
}

async function openPage(scenario: Scenario = "happy") {
  server.use(...handlersFor(scenario));
  render(
    <ThemeProvider storageKey={null}>
      <DiscoverPage />
    </ThemeProvider>,
  );
  if (scenario !== "map-down") await waitFor(() => expect(screen.getByText(/^Map of 5 tracks/)).toBeInTheDocument());
}

async function search() {
  await userEvent.type(screen.getByRole("textbox", { name: "Search by describing a sound" }), "chill flute{Enter}");
  return screen.findByRole("list", { name: "Ranked results" });
}

const summary = () => screen.getByText(/^Map of \d+ tracks/);
const target = () => deck.props!.viewState.target.slice(0, 2);
const row = (list: HTMLElement, title: string) => within(list).getAllByRole("listitem").find((li) => li.parentElement === list && li.textContent?.includes(title))!;

describe("map container", () => {
  it("search results light up on the map and the rest dim; results without coordinates are 'not on map'", async () => {
    await openPage();
    expect(summary()).toHaveTextContent("Map of 5 tracks.");
    await search();
    const onMap = RESULTS.filter((r) => r.spatial !== null).length;
    await waitFor(() => expect(summary()).toHaveTextContent(`Map of 5 tracks; ${onMap} results highlighted`));
    expect(screen.getAllByText(/not on (the )?map/i)).toHaveLength(RESULTS.length - onMap);
    // the camera fits the results where their points are drawn: their centre
    const [a, b] = RESULTS.filter((r) => r.spatial).map((r) => point(r.track_id));
    expect(target()[0]).toBeCloseTo((a!.x + b!.x) / 2);
  });

  it("a map click selects the track: its row is current and the camera eases to it; SELECT_TRACK only in a session", async () => {
    await openPage();
    const feedback = record("/api/feedback");
    const p = point("trk_example_2");
    act(() => deck.props!.onClick({ object: p }));
    expect(target()).toEqual([p.x, p.y]);
    expect(feedback).toHaveLength(0); // D4: no search yet, so nothing is recorded

    const list = await search();
    act(() => deck.props!.onClick({ object: p }));
    expect(row(list, p.title!)).toHaveAttribute("aria-current", "true");
    await waitFor(() => expect(feedback).toHaveLength(1));
    expect(feedback[0]!.body).toMatchObject({ event_type: "SELECT_TRACK", track_id: p.track_id });
    expect(within(row(list, p.title!)).queryByRole("status")).toBeNull(); // not shown as row feedback
  });

  it("a row click selects the point on the map", async () => {
    await openPage();
    const list = await search();
    const r = RESULTS[0]!;
    await userEvent.click(within(list).getByRole("button", { name: r.title }));
    const layer = deck.props!.layers[0]!.props;
    expect((layer.updateTriggers as Record<string, string>).getLineColor).toBeTruthy();
    expect(target()).toEqual([point(r.track_id).x, point(r.track_id).y]);
    expect(row(list, r.title)).toHaveAttribute("aria-current", "true");
  });

  it("hover cross-highlights: a point hovers its row, a row hovers its point", async () => {
    await openPage();
    const list = await search();
    const p = point("trk_example_1");
    act(() => deck.props!.onHover({ object: p, x: 10, y: 10 }));
    expect(row(list, p.title!).className).toMatch(/bg-surface-raised/);
    expect(screen.getByText(p.title!, { selector: "[role=tooltip] *, [role=tooltip]" })).toBeInTheDocument();
    act(() => deck.props!.onHover({ object: null, x: 0, y: 0 }));
    const before = JSON.stringify(deck.props!.layers[0]!.props.updateTriggers);
    await userEvent.hover(row(list, RESULTS[1]!.title));
    expect(JSON.stringify(deck.props!.layers[0]!.props.updateTriggers)).not.toBe(before);
  });

  it("reset view clears the highlight but keeps the list", async () => {
    await openPage();
    await search();
    await userEvent.click(screen.getByRole("button", { name: "Reset view" }));
    expect(summary()).toHaveTextContent("Map of 5 tracks.");
    expect(screen.getByRole("list", { name: "Ranked results" })).toBeInTheDocument();
  });

  it("the legend filters the points by genre and clears on the second click; no audio-only toggle", async () => {
    await openPage();
    const requests = record("/api/map/points");
    const legend = screen.getByRole("region", { name: "Genre legend" });
    await userEvent.click(within(legend).getByRole("button", { name: /Folk/ }));
    await waitFor(() => expect(requests.some((r) => new URL(r.url).searchParams.get("genre") === "Folk")).toBe(true));
    await userEvent.click(within(screen.getByRole("region", { name: "Genre legend" })).getByRole("button", { name: /Folk/ }));
    await waitFor(() => expect(new URL(requests.at(-1)!.url).searchParams.get("genre")).toBeNull());
    // every point is from the audio projection, so an audio filter would do nothing
    expect(screen.queryByRole("button", { name: "Only tracks with audio" })).toBeNull();
  });

  it("the legend is open on the idle map and collapses beside results, unless the user chose", async () => {
    await openPage();
    expect(screen.getByRole("region", { name: "Genre legend" })).toBeInTheDocument();
    await search();
    expect(screen.queryByRole("region", { name: "Genre legend" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Genre legend" }));
    expect(screen.getByRole("region", { name: "Genre legend" })).toBeInTheDocument();
  });

  it("the list alternative selects like the map", async () => {
    await openPage();
    const list = await search();
    await userEvent.click(screen.getByRole("button", { name: "List of map tracks" }));
    const alt = screen.getByRole("region", { name: "Tracks on the map" });
    await userEvent.click(within(alt).getByRole("button", { name: /Example Track 2/ }));
    expect(row(list, "Example Track 2")).toHaveAttribute("aria-current", "true");
  });

  it("a WebGL failure falls back to the list", async () => {
    await openPage();
    act(() => deck.props!.onError(new Error("WebGL context lost")));
    expect(screen.getByRole("status")).toHaveTextContent("couldn't draw the map");
    expect(screen.getByRole("region", { name: "Tracks on the map" })).toBeInTheDocument();
  });

  it("map down: the map explains itself and search is fully usable", async () => {
    await openPage("map-down");
    expect(await screen.findByText("Map is unavailable — search still works.")).toBeInTheDocument();
    expect(screen.queryByRole("toolbar", { name: "Map controls" })).toBeNull();
    const list = await search();
    expect(within(list).getAllByText(/not on (the )?map/i).length).toBeGreaterThan(0);
    await userEvent.click(within(list).getByRole("button", { name: RESULTS[0]!.title }));
    expect(row(list, RESULTS[0]!.title)).toHaveAttribute("aria-current", "true");
  });
});

describe("render cost (docs/ui/performance.md)", () => {
  it("moving across one point re-renders the map, not the page, and keeps the point layer", async () => {
    let pageCommits = 0;
    server.use(...handlersFor("happy"));
    render(
      <ThemeProvider storageKey={null}>
        <Profiler id="page" onRender={() => (pageCommits += 1)}>
          <DiscoverPage />
        </Profiler>
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText(/^Map of 5 tracks/)).toBeInTheDocument());
    const p = point("trk_example_1");
    act(() => deck.props!.onHover({ object: p, x: 1, y: 1 }));
    const layer = deck.props!.layers[0];
    const before = pageCommits;
    for (let x = 2; x < 12; x++) act(() => deck.props!.onHover({ object: p, x, y: x }));
    // the tooltip follows the pointer inside TrackMap; the page's hovered id doesn't change
    expect(deck.props!.layers[0]).toBe(layer);
    expect(pageCommits - before).toBeLessThanOrEqual(10); // one small commit per move at most (TrackMap only)
  });

  it("a refinement settles in a handful of page commits", async () => {
    let commits = 0;
    server.use(...handlersFor("happy"));
    render(
      <ThemeProvider storageKey={null}>
        <Profiler id="page" onRender={() => (commits += 1)}>
          <DiscoverPage />
        </Profiler>
      </ThemeProvider>,
    );
    await search();
    await waitFor(() => expect(screen.getByText(/2 results highlighted/)).toBeInTheDocument());
    const before = commits;
    await userEvent.click(screen.getByRole("button", { name: "Less like this: Example Track 1" }));
    await screen.findByRole("region", { name: "What changed" });
    await waitFor(() => expect(screen.getByText(/results highlighted/)).toBeInTheDocument());
    const spent = commits - before;
    expect(spent).toBeLessThanOrEqual(12);
  });
});

describe("selection helpers", () => {
  it("keeps only results with coordinates from this projection", () => {
    const { ids, bounds } = resultsOnMap(RESULTS, [], "umap-example");
    expect([...ids]).toEqual(["trk_example_1", "trk_example_2"]);
    const [one, two] = [point("trk_example_1"), point("trk_example_2")];
    expect(bounds).toEqual({ min_x: one.x, max_x: two.x, min_y: two.y, max_y: one.y });
    expect(resultsOnMap(RESULTS, [], "umap-other").ids.size).toBe(0);
    expect(resultsOnMap(RESULTS, [], null).bounds).toBeNull();
    // loaded points win: the camera fits where the dots are drawn
    const drawn = resultsOnMap(RESULTS, POINTS, "umap-example").bounds!;
    expect(drawn.min_x).toBe(Math.min(point("trk_example_1").x, point("trk_example_2").x));
  });

  it("locates a track by its point, else by a same-projection result", () => {
    expect(locate("trk_example_2", POINTS, [], "umap-example")).toMatchObject({ x: point("trk_example_2").x });
    expect(locate("trk_example_1", [], RESULTS, "umap-example")).toMatchObject({ x: point("trk_example_1").x, y: point("trk_example_1").y });
    expect(locate("trk_example_1", [], RESULTS, "umap-other")).toBeNull();
    expect(pointBounds({ x: 1, y: 2 })).toEqual({ min_x: 1, max_x: 1, min_y: 2, max_y: 2 });
  });

  it("changes one filter and keeps the others", () => {
    expect(withGenre({ has_audio: true }, "Folk")).toEqual({ has_audio: true, genre: "Folk" });
    expect(withGenre({ has_audio: true, genre: "Folk" }, null)).toEqual({ has_audio: true });
  });
});
