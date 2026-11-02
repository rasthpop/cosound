// The Discover screen in mock mode (U04): search, refine with feedback, and the map in sync.
import { expect, test } from "@playwright/test";

import { open, screenPosition, search } from "./helpers";

test.skip(process.env.E2E_REAL_BACKEND === "1", "mock-mode flows");

test.describe("feedback & refinement", () => {
  test("👎 on a row refreshes the plate and says what changed", async ({ page }) => {
    await open(page);
    await search(page);
    const row = page.getByRole("list", { name: "Ranked results" }).getByRole("listitem").filter({ hasText: "Example Track 1" }).first();
    await row.hover();
    const response = page.waitForResponse((r) => r.url().endsWith("/api/feedback"));
    await row.getByRole("button", { name: "Less like this: Example Track 1" }).click();
    expect((await response).ok()).toBe(true);
    const strip = page.getByRole("region", { name: "What changed" });
    await expect(strip).toContainText("Removed “Example Track 1”");
    await expect(strip).toContainText("Refined “Something chill with a flute”");
    // the map highlight follows the refreshed plate (flow 4)
    await expect(page.getByRole("region", { name: "Map of tracks by audio similarity" })).toContainText("2 results highlighted");
  });

  test("feedback the backend rejects shows its reason", async ({ page }) => {
    await open(page);
    await search(page);
    await page.getByRole("button", { name: "Refine the current results" }).click();
    await page.getByRole("textbox", { name: "Refine the current results" }).fill("lovely weather");
    await page.keyboard.press("Enter");
    await expect(page.getByText("Not applied: nothing in the feedback text maps to a known attribute")).toBeVisible();
  });

  test("hard-constraint chips send nothing", async ({ page }) => {
    await open(page, "no-confident-match");
    await page.getByRole("textbox", { name: "Search by describing a sound" }).fill("instrumental only flute");
    await page.keyboard.press("Enter");
    const chips = page.getByRole("region", { name: "What the search understood" });
    await expect(chips).toBeVisible();
    let sent = 0;
    page.on("request", (r) => {
      if (r.url().endsWith("/api/feedback")) sent += 1;
    });
    const hard = chips.getByRole("listitem").filter({ hasText: /vocals/i }).first();
    await expect(hard.getByRole("button")).toHaveCount(0);
    await hard.click();
    await page.waitForTimeout(300);
    expect(sent).toBe(0);
  });
});

// ── map ⇄ plate (U04.T03) ──
// Under reduced motion the camera moves instantly, so a point's screen position follows from the
// same fit the map uses: the whole projection after "Reset view".

test.describe("map & selection", () => {
  test.use({ reducedMotion: "reduce" });

  test("results light up and the rest dim; a map click selects the row; a row click selects the point", async ({ page }) => {
    await open(page);
    await search(page);
    const map = page.getByRole("region", { name: "Map of tracks by audio similarity" });
    await expect(map).toContainText("2 results highlighted");
    const rows = page.getByRole("list", { name: "Ranked results" });

    await page.getByRole("button", { name: "Reset view" }).click();
    await expect(map).not.toContainText("results highlighted");
    const at = screenPosition(page, "trk_example_2");
    await page.mouse.click(at.x, at.y);
    await expect(rows.getByRole("listitem").filter({ hasText: "Example Track 2" }).first()).toHaveAttribute("aria-current", "true");
    // …and opens its details (the mock serves the same detail fixture for every id)
    const details = page.getByRole("dialog");
    await expect(details).toBeVisible();
    await expect(details.getByRole("region", { name: /nearby|sound/i })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(details).toBeHidden();

    await rows.getByRole("button", { name: "Example Track 1", exact: true }).click();
    await page.getByRole("button", { name: "List of map tracks" }).click();
    const alt = page.getByRole("region", { name: "Tracks on the map" });
    await expect(alt.getByRole("button", { name: /Example Track 1/ })).toHaveAttribute("aria-current", "true");
    await expect(alt.getByRole("button", { name: /Example Track 2/ })).not.toHaveAttribute("aria-current", "true");
  });

  test("map down: search stays fully usable", async ({ page }) => {
    await open(page, "map-down");
    await expect(page.getByText("Map is unavailable — search still works.")).toBeVisible();
    await search(page);
    await expect(page.getByText("Map unavailable", { exact: true })).toBeVisible();
    const rows = page.getByRole("list", { name: "Ranked results" });
    await rows.getByRole("button", { name: "Example Track 1", exact: true }).click();
    await expect(rows.getByRole("listitem").filter({ hasText: "Example Track 1" }).first()).toHaveAttribute("aria-current", "true");
  });
});
