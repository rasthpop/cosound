// The Discover screen against the MSW contract mocks, one scenario per state (ux-states-and-evidence §1).
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { fixture } from "@/mocks/fixtures";
import { handlersFor } from "@/mocks/handlers";
import type { Scenario } from "@/mocks/scenarios";
import { server } from "@/mocks/server";
import { ThemeProvider } from "@/theme/ThemeProvider";

import { announceSearch, EXAMPLE_QUERIES } from "./copy";
import { DiscoverPage } from "./DiscoverPage";

afterEach(cleanup);

function renderPage(scenario: Scenario = "happy") {
  server.use(...handlersFor(scenario));
  render(
    <ThemeProvider storageKey={null}>
      <DiscoverPage />
    </ThemeProvider>,
  );
  return { input: screen.getByRole("textbox", { name: "Search by describing a sound" }) };
}

async function searchFor(text = "chill flute", scenario: Scenario = "happy") {
  const page = renderPage(scenario);
  await userEvent.type(page.input, `${text}{Enter}`);
  return page;
}

const liveRegion = () => document.querySelector('[aria-live="polite"][aria-atomic="true"]');
const resultsPanel = () => screen.getByRole("region", { name: /^(\d+ tracks?|No tracks|Results)$/ });

describe("DiscoverPage", () => {
  it("idle: focuses the input and shows the example queries, with no results panel", async () => {
    const { input } = renderPage();
    expect(input).toHaveFocus();
    for (const example of EXAMPLE_QUERIES) expect(screen.getByRole("button", { name: example })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Ranked results" })).toBeNull();
  });

  it("`/` focuses the input from anywhere, but types normally inside it", async () => {
    const { input } = renderPage();
    input.blur();
    await userEvent.keyboard("/");
    expect(input).toHaveFocus();
    await userEvent.keyboard("a/b");
    expect(input).toHaveValue("a/b");
  });

  it("happy: shows the plate in API order, the chips, and announces the count", async () => {
    await searchFor();
    const list = await screen.findByRole("list", { name: "Ranked results" });
    const titles = fixture("search_ok").results.map((r) => r.title);
    const rows = within(list).getAllByRole("listitem").filter((li) => li.parentElement === list);
    // the title is each row's first button
    expect(rows.map((r) => within(r).getAllByRole("button")[0]!.textContent)).toEqual(titles);
    expect(screen.getByRole("region", { name: "What the search understood" })).toBeInTheDocument();
    expect(within(resultsPanel()).getByRole("heading", { name: "3 tracks" })).toBeInTheDocument();
    expect(liveRegion()).toHaveTextContent("3 results for “Something chill with a flute”");
  });

  it("an example query runs a search", async () => {
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: EXAMPLE_QUERIES[0] }));
    expect(await screen.findByRole("list", { name: "Ranked results" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Search by describing a sound" })).toHaveValue(EXAMPLE_QUERIES[0]);
  });

  it("empty: says nothing matched and offers to edit the search", async () => {
    const { input } = await searchFor("xyz", "empty");
    expect(await screen.findByText("No tracks matched")).toBeInTheDocument();
    expect(liveRegion()).toHaveTextContent("No results for");
    await userEvent.clear(input);
    await userEvent.click(screen.getAllByRole("button", { name: "Edit your search" })[0]!);
    expect(input).toHaveValue("Something chill with a flute");
    expect(input).toHaveFocus();
  });

  it("no confident match: shows the reasons as given", async () => {
    await searchFor("instrumental only flute", "no-confident-match");
    expect(await screen.findByText("No confident match")).toBeInTheDocument();
    for (const reason of fixture("search_no_confident_match").no_match_reasons) expect(screen.getByText(reason)).toBeInTheDocument();
    expect(liveRegion()).toHaveTextContent("No confident match for");
  });

  it("needs clarification: asks the question under the bar and replies with a follow-up search", async () => {
    await searchFor("no vocals with female vocals", "needs-clarification");
    const question = fixture("search_needs_clarification").clarification_question!;
    expect(await screen.findByText(question)).toBeInTheDocument();
    expect(liveRegion()).toHaveTextContent(question);
    const bodies: unknown[] = [];
    server.events.on("request:start", async ({ request }) => {
      if (request.url.endsWith("/api/search")) bodies.push(await request.clone().json());
    });
    await userEvent.type(screen.getByPlaceholderText("Your answer"), "no vocals");
    await userEvent.click(screen.getByRole("button", { name: "Reply" }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toMatchObject({ query: "no vocals", session_id: fixture("search_needs_clarification").session_id });
    server.events.removeAllListeners();
  });

  it("degraded semantic: the pill says sound-based matching is off, and results still show", async () => {
    await searchFor("chill flute", "degraded-semantic");
    expect(await screen.findByRole("list", { name: "Ranked results" })).toBeInTheDocument();
    expect(screen.getByText("Sound-based matching is off — catalog data only")).toBeInTheDocument();
  });

  it("degraded semantic before any search: the pill comes from the health check", async () => {
    renderPage("degraded-semantic");
    expect(await screen.findByText("Sound-based matching is off — catalog data only")).toBeInTheDocument();
  });

  it("map down: the pill says so, and search works", async () => {
    await searchFor("chill flute", "map-down");
    expect(await screen.findByRole("list", { name: "Ranked results" })).toBeInTheDocument();
    expect(await screen.findByText("Map unavailable")).toBeInTheDocument();
  });

  it("LLM fallback: a subtle note under the chips, no pill", async () => {
    await searchFor("chill flute", "llm-fallback");
    expect(await screen.findByText(/built-in parser/)).toBeInTheDocument();
    expect(screen.queryByText("Sound-based matching is off — catalog data only")).toBeNull();
  });

  it("offline: keeps the typed query, explains, and retries", async () => {
    const { input } = await searchFor("chill flute", "offline");
    expect(await screen.findByText("You're offline")).toBeInTheDocument();
    expect(input).toHaveValue("chill flute");
    expect(screen.getByText(/Your search “chill flute” is kept/)).toBeInTheDocument();
    expect(await screen.findByText("Offline")).toBeInTheDocument(); // the pill
    server.use(...handlersFor("happy"));
    await userEvent.click(within(screen.getByRole("alert")).getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("list", { name: "Ranked results" })).toBeInTheDocument();
  });

  it("error: a human message and a retry, no technical detail", async () => {
    await searchFor("chill flute", "errors");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Search didn't work");
    expect(alert).not.toHaveTextContent("internal_error");
    expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("selecting a row marks it as current", async () => {
    await searchFor();
    const list = await screen.findByRole("list", { name: "Ranked results" });
    const first = fixture("search_ok").results[0]!;
    await userEvent.click(within(list).getByRole("button", { name: first.title }));
    expect(within(list).getAllByRole("listitem").find((li) => li.getAttribute("aria-current") === "true")).toHaveTextContent(first.title);
  });
});

describe("announceSearch", () => {
  const ok = fixture("search_ok");
  it("counts results and handles the other outcomes", () => {
    expect(announceSearch(ok, "q")).toBe("3 results for “q”");
    expect(announceSearch({ ...ok, results: ok.results.slice(0, 1) }, "q")).toBe("1 result for “q”");
    expect(announceSearch(fixture("search_empty"), "q")).toBe("No results for “q”");
    expect(announceSearch(fixture("search_no_confident_match"), "q")).toBe("No confident match for “q”");
    expect(announceSearch(fixture("search_needs_clarification"), "q")).toMatch(/needs more detail: Should the music/);
  });
});
