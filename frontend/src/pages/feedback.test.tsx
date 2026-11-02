// Feedback and refinement on the Discover screen, against the MSW contract mocks (flow 4).
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import type { FeedbackState } from "@/hooks";
import { fixture } from "@/mocks/fixtures";
import { handlersFor } from "@/mocks/handlers";
import type { Scenario } from "@/mocks/scenarios";
import { server } from "@/mocks/server";
import { ThemeProvider } from "@/theme/ThemeProvider";

import { DiscoverPage } from "./DiscoverPage";
import { feedbackMessage, feedbackStatus, queryInstruments, stripFor } from "./feedback";

afterEach(() => {
  cleanup();
  server.events.removeAllListeners();
});

/** Bodies of the feedback requests the mock received. */
function recordFeedback() {
  const bodies: Record<string, unknown>[] = [];
  server.events.on("request:start", async ({ request }) => {
    if (request.url.endsWith("/api/feedback")) bodies.push((await request.clone().json()) as Record<string, unknown>);
  });
  return bodies;
}

async function searchFor(scenario: Scenario = "happy") {
  server.use(...handlersFor(scenario));
  render(
    <ThemeProvider storageKey={null}>
      <DiscoverPage />
    </ThemeProvider>,
  );
  const input = screen.getByRole("textbox", { name: "Search by describing a sound" });
  await userEvent.type(input, "chill flute{Enter}");
  return { input };
}

const liveRegion = () => document.querySelector('[aria-live="polite"][aria-atomic="true"]');

describe("feedback on the Discover screen", () => {
  it("👎 on a row refreshes the plate from the server and shows what changed", async () => {
    await searchFor();
    const bodies = recordFeedback();
    const first = fixture("search_ok").results[0]!;
    await userEvent.click(await screen.findByRole("button", { name: `Less like this: ${first.title}` }));
    const strip = await screen.findByRole("region", { name: "What changed" });
    expect(strip).toHaveTextContent(`Removed “${first.title}”`);
    expect(strip).toHaveTextContent("Refined “Something chill with a flute”");
    expect(bodies[0]).toMatchObject({ event_type: "LESS_LIKE_THIS", track_id: first.track_id, refresh: true });
    // the plate is the response's `refreshed` one (the mock re-serves search_ok's three tracks)
    expect(screen.getByRole("heading", { name: "3 tracks" })).toBeInTheDocument();
    expect(liveRegion()).toHaveTextContent("Results refined. 3 results for “Something chill with a flute”");
    await userEvent.click(within(strip).getByRole("button", { name: "Dismiss what changed" }));
    expect(screen.queryByRole("region", { name: "What changed" })).toBeNull();
  });

  it("a soft chip sends More/Less of that attribute", async () => {
    await searchFor();
    const bodies = recordFeedback();
    const chips = await screen.findByRole("region", { name: "What the search understood" });
    await userEvent.click(within(chips).getByRole("button", { name: "flute: adjust" }));
    await userEvent.click(await screen.findByRole("button", { name: "Less of this" }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toMatchObject({ event_type: "LESS_OF_ATTRIBUTE", attribute: "instrument", value: "flute", refresh: true });
    expect(await screen.findByRole("region", { name: "What changed" })).toBeInTheDocument();
  });

  it("hard-constraint chips send nothing", async () => {
    await searchFor("no-confident-match");
    const bodies = recordFeedback();
    const chips = await screen.findByRole("region", { name: "What the search understood" });
    const hard = within(chips).getByText(/vocals/i).closest("li")!;
    expect(within(hard).queryAllByRole("button")).toHaveLength(0);
    await userEvent.click(hard);
    expect(bodies).toHaveLength(0);
  });

  it("free text the backend can't map is shown as not applied, with its reason", async () => {
    const { input } = await searchFor();
    await screen.findByRole("list", { name: "Ranked results" });
    await userEvent.click(screen.getByRole("button", { name: "Refine the current results" }));
    await userEvent.clear(input);
    await userEvent.type(input, "lovely weather{Enter}");
    const reason = fixture("feedback_rejected").reason!;
    expect(await screen.findByText(`Not applied: ${reason}`)).toBeInTheDocument();
    // the plate is unchanged
    expect(screen.getByRole("heading", { name: "3 tracks" })).toBeInTheDocument();
  });

  it("a failed row feedback says why on the row", async () => {
    await searchFor();
    server.use(http.post("*/api/feedback", () => Response.json(fixture("error_track_not_in_results"), { status: 409 })));
    const first = fixture("search_ok").results[0]!;
    await userEvent.click(await screen.findByRole("button", { name: `More like this: ${first.title}` }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't send: That track is no longer in the results.");
    expect(screen.queryByRole("region", { name: "What changed" })).toBeNull();
  });

  it("“Edit your search” prefills the input with the original query", async () => {
    const { input } = await searchFor("no-confident-match");
    await userEvent.clear(input);
    await userEvent.click((await screen.findAllByRole("button", { name: "Edit your search" }))[0]!);
    expect(input).toHaveValue(fixture("search_no_confident_match").interpreted_query.original_query);
  });
});

describe("feedback helpers", () => {
  const refined = fixture("feedback_refined");
  const rejected = fixture("feedback_rejected");
  const state = (s: Partial<FeedbackState>): FeedbackState => ({ status: "idle", error: null, response: null, ...s });

  it("maps hook state to the view's acknowledgement", () => {
    expect(feedbackStatus(undefined)).toBe("idle");
    expect(feedbackStatus(state({ status: "loading" }))).toBe("pending");
    expect(feedbackStatus(state({ status: "success", response: refined }))).toBe("applied");
    expect(feedbackStatus(state({ status: "success", response: rejected }))).toBe("rejected");
    expect(feedbackStatus(state({ status: "error" }))).toBe("error");
  });

  it("gives the reason or a human error message", () => {
    expect(feedbackMessage(state({ status: "success", response: rejected }))).toBe(rejected.reason);
    expect(feedbackMessage(state({ status: "success", response: refined }))).toBeNull();
    const error = { kind: "http" as const, code: "track_not_in_results", message: "x", status: 409, details: {} };
    expect(feedbackMessage(state({ status: "error", error }))).toMatch(/no longer in the results/);
  });

  it("builds the strip only once a submission settled", () => {
    expect(stripFor(state({ status: "loading" }))).toBeNull();
    expect(stripFor(state({ status: "success", response: refined }))).toMatchObject({ status: "applied", response: refined });
  });

  it("offers the query's instruments for “Wrong instrument…”", () => {
    expect(queryInstruments(fixture("search_ok").interpreted_query)).toEqual(["flute"]);
    expect(queryInstruments(null)).toEqual([]);
  });
});
