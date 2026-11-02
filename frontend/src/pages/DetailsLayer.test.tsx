// The details drawer inside the Discover screen, against the MSW mocks (ui.md §4.4, §7). DeckGL
// is stubbed as in MapLayer.test.tsx so the camera can be observed.
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MapPoint } from "@/api/types";
import { fixture } from "@/mocks/fixtures";
import { handlersFor } from "@/mocks/handlers";
import { server } from "@/mocks/server";
import { ThemeProvider } from "@/theme/ThemeProvider";

import { pauseOthers } from "./audio";
import { DiscoverPage } from "./DiscoverPage";

type DeckProps = {
  viewState: { target: number[]; zoom: number };
  onClick: (info: { object: MapPoint | null }) => void;
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

async function openPage() {
  server.use(...handlersFor("happy"));
  render(
    <ThemeProvider storageKey={null}>
      <DiscoverPage />
    </ThemeProvider>,
  );
  await waitFor(() => expect(screen.getByText(/^Map of 5 tracks/)).toBeInTheDocument());
}

async function search() {
  await userEvent.type(screen.getByRole("textbox", { name: "Search by describing a sound" }), "chill flute{Enter}");
  return screen.findByRole("list", { name: "Ranked results" });
}

const drawer = () => screen.findByRole("dialog");

describe("details drawer", () => {
  it("opens from a row with the plate's description and reasons, and returns focus to the row on close", async () => {
    await openPage();
    const list = await search();
    const r = fixture("search_ok").results[0]!;
    const title = within(list).getByRole("button", { name: r.title });
    await userEvent.click(title);
    const panel = await drawer();
    expect(await within(panel).findByRole("heading", { name: r.title })).toBeInTheDocument();
    expect(within(panel).getByText(r.description!)).toBeInTheDocument();
    expect(within(panel).getByText("How it matched")).toBeInTheDocument(); // score bands from the plate
    expect(within(panel).getByRole("group", { name: `Feedback on ${r.title}` })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(title).toHaveFocus();
  });

  it("from the map (no search): catalog facts only, no plate evidence or feedback; focus returns to the map", async () => {
    await openPage();
    act(() => deck.props!.onClick({ object: point("trk_example_1") }));
    const panel = await drawer();
    expect(await within(panel).findByRole("heading", { name: "Example Track 1" })).toBeInTheDocument();
    expect(within(panel).queryByText("How it matched")).toBeNull();
    expect(within(panel).queryByRole("group", { name: /Feedback on/ })).toBeNull();
    expect(screen.queryByRole("list", { name: "Ranked results" })).toBeNull(); // free browse: no panel
    await userEvent.click(within(panel).getByRole("button", { name: "Close details" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByRole("region", { name: "Map of tracks arranged by audio similarity (approximate)" })).toHaveFocus();
  });

  it("a neighbor click selects that track and moves the camera", async () => {
    await openPage();
    act(() => deck.props!.onClick({ object: point("trk_example_1") }));
    const panel = await drawer();
    const nearby = await within(panel).findByRole("region", { name: /nearby|sound/i });
    const requested: string[] = [];
    server.events.on("request:start", ({ request }) => requested.push(new URL(request.url).pathname));
    await userEvent.click(within(nearby).getByRole("button", { name: /Example Track 2/ }));
    expect(deck.props!.viewState.target.slice(0, 2)).toEqual([point("trk_example_2").x, point("trk_example_2").y]);
    await waitFor(() => expect(requested).toContain("/api/tracks/trk_example_2"));
    server.events.removeAllListeners();
  });

  it("a track without audio says so", async () => {
    // tracks without audio are not on the audio map: open one from the results
    await openPage();
    const list = await search();
    await userEvent.click(within(list).getByRole("button", { name: "Example Track 3" }));
    const panel = await drawer();
    expect(await within(panel).findByText("No audio preview available.")).toBeInTheDocument();
    // and why: no audio analysis, said once (evidence status and flag agree)
    expect(within(panel).getByText("No audio analysis for this track")).toBeInTheDocument();
  });

  it("from the map, the drawer still says what evidence the track has, and labels FMA tags as such", async () => {
    await openPage();
    act(() => deck.props!.onClick({ object: point("trk_example_1") }));
    const panel = await drawer();
    expect(await within(panel).findByRole("list", { name: "FMA tags" })).toHaveTextContent("flute");
    expect(within(panel).getByRole("list", { name: "FMA genres" })).toHaveTextContent("Folk");
    // a track with audio and catalog data has nothing to caveat
    expect(within(panel).queryByText(/No audio analysis/)).toBeNull();
  });

  it("one clip at a time: a second row play pauses the first, and the drawer's player stops the rows", async () => {
    await openPage();
    const list = await search();
    const [a, b] = fixture("search_ok").results;
    await userEvent.click(within(list).getByRole("button", { name: `Play ${a!.title}` }));
    expect(within(list).getByRole("button", { name: `Pause ${a!.title}` })).toBeInTheDocument();
    await userEvent.click(within(list).getByRole("button", { name: `Play ${b!.title}` }));
    expect(within(list).getByRole("button", { name: `Play ${a!.title}` })).toBeInTheDocument();
    expect(within(list).getByRole("button", { name: `Pause ${b!.title}` })).toBeInTheDocument();

    await userEvent.click(within(list).getByRole("button", { name: a!.title }));
    const panel = await drawer();
    const player = await within(panel).findByLabelText(`Preview of ${a!.title}`);
    act(() => {
      player.dispatchEvent(new Event("play"));
    });
    expect(within(list).getByRole("button", { name: `Play ${b!.title}` })).toBeInTheDocument();
  });
});

describe("pauseOthers", () => {
  it("pauses every playing <audio> except the one that started", () => {
    const root = document.createElement("div");
    const [first, second, idle] = [0, 1, 2].map(() => root.appendChild(document.createElement("audio")));
    const playing = (el: HTMLAudioElement, on: boolean) => Object.defineProperty(el, "paused", { value: !on, configurable: true });
    playing(first!, true);
    playing(second!, true);
    playing(idle!, false);
    const pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(function (this: HTMLMediaElement) {
      Object.defineProperty(this, "paused", { value: true, configurable: true });
    });
    pauseOthers(second!, root);
    expect(pause).toHaveBeenCalledTimes(1);
    expect(first!.paused).toBe(true);
    expect(second!.paused).toBe(false);
  });
});
