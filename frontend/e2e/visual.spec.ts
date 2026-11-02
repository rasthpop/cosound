// Visual baselines of the Discover screen (U05.T02): key states per theme, at desktop (1280 px)
// and phone (390 px) widths, on the mock fixtures. Update deliberately with
//   npx playwright test e2e/visual.spec.ts --update-snapshots
// and review the changed images in the diff.
import { expect, test, type Page } from "@playwright/test";

import { open, search, searchInput } from "./helpers";

test.skip(process.env.E2E_REAL_BACKEND === "1", "mock-mode baselines");

const WIDTHS = { desktop: { width: 1280, height: 800 }, phone: { width: 390, height: 844 } } as const;
const THEMES = ["dark", "light"] as const;

/** Wait until nothing is loading, so the shot is of a settled state. */
async function settled(page: Page) {
  await expect(page.getByRole("progressbar", { name: "Searching" })).toHaveCount(0, { timeout: 10_000 });
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, { timeout: 10_000 });
  await page.waitForTimeout(300); // the map draws on the next frames
}

const STATES: Record<string, (page: Page) => Promise<void>> = {
  idle: async (page) => {
    await open(page);
    await expect(page.getByText("Map of 5 tracks")).toBeAttached();
  },
  results: async (page) => {
    await open(page);
    await search(page);
  },
  refined: async (page) => {
    await open(page);
    await search(page);
    // by keyboard: on phone the sheet may still be sliding in, which can make a pointer click miss
    await page.getByRole("button", { name: "Less like this: Example Track 1" }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("region", { name: "What changed" })).toBeVisible();
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  },
  details: async (page) => {
    await open(page);
    await search(page);
    await page.getByRole("list", { name: "Ranked results" }).getByRole("button", { name: "Example Track 1", exact: true }).click();
    await expect(page.getByRole("dialog").getByRole("region", { name: /nearby|sound/i })).toBeVisible();
  },
  "map-down": async (page) => {
    await open(page, "map-down");
    await search(page);
  },
  "no-confident-match": async (page) => {
    await open(page, "no-confident-match");
    await searchInput(page).fill("instrumental only flute");
    await page.keyboard.press("Enter");
    await expect(page.getByText("No confident match", { exact: true })).toBeVisible();
  },
  "needs-clarification": async (page) => {
    await open(page, "needs-clarification");
    await searchInput(page).fill("no vocals with female vocals");
    await page.keyboard.press("Enter");
    await expect(page.getByPlaceholder("Your answer")).toBeVisible();
  },
  offline: async (page) => {
    await open(page, "offline");
    await searchInput(page).fill("chill flute");
    await page.keyboard.press("Enter");
    await expect(page.getByText("You're offline")).toBeVisible();
  },
};

for (const theme of THEMES) {
  for (const [width, viewport] of Object.entries(WIDTHS)) {
    test.describe(`${theme} · ${width}`, () => {
      test.use({ colorScheme: theme, viewport, reducedMotion: "reduce" });
      for (const [state, reach] of Object.entries(STATES)) {
        test(state, async ({ page }) => {
          await reach(page);
          await settled(page);
          await expect(page).toHaveScreenshot(`${state}-${theme}-${width}.png`);
        });
      }
    });
  }
}
