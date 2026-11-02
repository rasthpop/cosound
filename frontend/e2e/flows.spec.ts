// The five core flows of ui.md §5, run against every mock scenario (U05.T02). Each scenario says
// what the user should see; a flow that can't apply (no results to refine, no map to browse)
// checks that the screen says so instead.
import { expect, test, type Page } from "@playwright/test";

import { MAP_REGION, open, screenPosition, searchInput } from "./helpers";

test.skip(process.env.E2E_REAL_BACKEND === "1", "mock-mode flows");
test.use({ reducedMotion: "reduce", viewport: { width: 1280, height: 800 } });

type Outcome = "results" | "empty" | "no-confident-match" | "clarification" | "error" | "offline";

interface Expectation {
  outcome: Outcome;
  /** Is the map drawn? */
  map: boolean;
  /** Does opening details work (the track endpoint answers)? */
  details: boolean;
  /** Text a degraded mode must show. */
  notice?: RegExp;
}

const SCENARIOS: Record<string, Expectation> = {
  happy: { outcome: "results", map: true, details: true },
  "degraded-semantic": { outcome: "results", map: true, details: true, notice: /Sound-based matching is off/ },
  "map-down": { outcome: "results", map: false, details: true, notice: /Map unavailable/ },
  "no-confident-match": { outcome: "no-confident-match", map: true, details: true },
  "needs-clarification": { outcome: "clarification", map: true, details: true },
  "slow-network": { outcome: "results", map: true, details: true },
  errors: { outcome: "error", map: false, details: false },
  empty: { outcome: "empty", map: true, details: true },
  "llm-fallback": { outcome: "results", map: true, details: true, notice: /built-in parser/ },
  offline: { outcome: "offline", map: false, details: false, notice: /^Offline$/ },
};

const TIMEOUT = { timeout: 10_000 };
const results = (page: Page) => page.getByRole("list", { name: "Ranked results" });

async function runSearch(page: Page) {
  await searchInput(page).fill("chill flute");
  await page.keyboard.press("Enter");
}

async function expectOutcome(page: Page, outcome: Outcome) {
  const panel = {
    results: results(page),
    empty: page.getByText("No tracks matched"),
    "no-confident-match": page.getByText("No confident match", { exact: true }),
    clarification: page.getByText("Should the music have vocals or not?", { exact: true }),
    error: page.getByRole("alert").filter({ hasText: "Search didn't work" }),
    offline: page.getByRole("alert").filter({ hasText: "You're offline" }),
  }[outcome];
  await expect(panel).toBeVisible(TIMEOUT);
}

for (const [scenario, expected] of Object.entries(SCENARIOS)) {
  test.describe(scenario, () => {
    test("1 · idle: full map, input focused, examples visible", async ({ page }) => {
      await open(page, scenario);
      await expect(searchInput(page)).toBeFocused();
      await expect(page.getByRole("button", { name: "something chill with a flute" })).toBeVisible();
      await expect(results(page)).toHaveCount(0);
      if (expected.map) await expect(page.getByRole("region", { name: MAP_REGION })).toContainText("Map of 5 tracks", TIMEOUT);
      else await expect(page.getByText("Map is unavailable — search still works.")).toBeVisible(TIMEOUT);
    });

    test("2 · search: progress, chips, results panel, highlight", async ({ page }) => {
      await open(page, scenario);
      await runSearch(page);
      await expectOutcome(page, expected.outcome);
      await expect(page.getByRole("progressbar", { name: "Searching" })).toHaveCount(0, TIMEOUT);
      if (expected.notice) await expect(page.getByText(expected.notice)).toBeVisible(TIMEOUT);
      if (expected.outcome === "results" || expected.outcome === "no-confident-match" || expected.outcome === "empty") {
        await expect(page.getByRole("region", { name: "What the search understood" })).toBeVisible();
      }
      if (expected.outcome === "results" && expected.map) {
        await expect(page.getByRole("region", { name: MAP_REGION })).toContainText("2 results highlighted");
      }
      if (expected.outcome === "offline") await expect(searchInput(page)).toHaveValue("chill flute");
    });

    test("3 · explore: row → details → neighbor", async ({ page }) => {
      test.skip(expected.outcome !== "results", "no results to explore in this scenario");
      await open(page, scenario);
      await runSearch(page);
      await results(page).getByRole("button", { name: "Example Track 1", exact: true }).click();
      const dialog = page.getByRole("dialog");
      await expect(dialog.getByRole("heading", { name: "Example Track 1" })).toBeVisible(TIMEOUT);
      const nearby = dialog.getByRole("region", { name: /nearby|sound/i });
      const next = page.waitForRequest((r) => r.url().endsWith("/api/tracks/trk_example_2"));
      await nearby.getByRole("button", { name: /Example Track 2/ }).click();
      await next;
      await expect(results(page).getByRole("listitem").filter({ hasText: "Example Track 2" }).first()).toHaveAttribute("aria-current", "true");
    });

    test("4 · refine: 👎 → refreshed plate → what changed", async ({ page }) => {
      test.skip(expected.outcome !== "results", "no results to refine in this scenario");
      await open(page, scenario);
      await runSearch(page);
      const row = results(page).getByRole("listitem").filter({ hasText: "Example Track 1" }).first();
      await row.hover();
      await row.getByRole("button", { name: "Less like this: Example Track 1" }).click();
      await expect(page.getByRole("region", { name: "What changed" })).toContainText("Removed “Example Track 1”", TIMEOUT);
      await expect(page.getByRole("heading", { name: /\d+ tracks?/ }).first()).toBeVisible();
      if (expected.map) await expect(page.getByRole("region", { name: MAP_REGION })).toContainText("results highlighted");
    });

    test("5 · free browse: no query, click a point → details, no results panel", async ({ page }) => {
      test.skip(!expected.map, "no map to browse in this scenario");
      await open(page, scenario);
      await expect(page.getByRole("region", { name: MAP_REGION })).toContainText("Map of 5 tracks", TIMEOUT);
      const at = screenPosition(page, "trk_example_2");
      await page.mouse.click(at.x, at.y);
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible(TIMEOUT);
      if (expected.details) await expect(dialog.getByRole("region", { name: /nearby|sound/i })).toBeVisible(TIMEOUT);
      else await expect(dialog.getByRole("alert")).toBeVisible(TIMEOUT);
      await expect(results(page)).toHaveCount(0);
    });
  });
}
