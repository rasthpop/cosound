// Slow smoke of the Discover screen against a running backend (fma_small), U05.T02. Opt-in:
//   make serve   # in the repo root
//   E2E_REAL_BACKEND=1 API_PROXY_TARGET=http://127.0.0.1:8000 npx playwright test e2e/real-backend.spec.ts
// It asserts only what any healthy install shows; it never assumes particular tracks.
import { expect, test } from "@playwright/test";

import { MAP_REGION, searchInput } from "./helpers";

test.skip(process.env.E2E_REAL_BACKEND !== "1", "needs a running backend (E2E_REAL_BACKEND=1)");
test.use({ reducedMotion: "reduce", viewport: { width: 1280, height: 800 } });

test("search, results on the map, details, refine", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/");
  await expect(searchInput(page)).toBeFocused();

  // the map either draws the projection or says it's unavailable; both keep search usable
  const map = page.getByRole("region", { name: MAP_REGION }).or(page.getByText("Map is unavailable — search still works."));
  await expect(map).toBeVisible({ timeout: 60_000 });

  await searchInput(page).fill("something chill with a flute");
  await page.keyboard.press("Enter");
  const rows = page.getByRole("list", { name: "Ranked results" });
  const settled = rows.or(page.getByText("No confident match", { exact: true })).or(page.getByText("No tracks matched")).or(page.getByPlaceholder("Your answer"));
  await expect(settled.first()).toBeVisible({ timeout: 120_000 });
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.locator('[aria-live="polite"][aria-atomic="true"]')).not.toBeEmpty();

  test.skip(!(await rows.isVisible()), "the catalog returned no plate for this query");
  // the first row's title opens details from the API
  const first = rows.locator(":scope > li").first();
  const title = (await first.getByRole("button").first().textContent())!.trim();
  await first.getByRole("button", { name: title, exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: title })).toBeVisible({ timeout: 30_000 });
  await page.keyboard.press("Escape");

  // feedback refreshes the plate from the server
  await first.hover();
  await first.getByRole("button", { name: `Less like this: ${title}` }).click();
  await expect(page.getByRole("region", { name: "What changed" })).toBeVisible({ timeout: 60_000 });
});
