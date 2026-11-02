// The Discover screen in mock mode (U04): search, refine with feedback, and the map in sync.
import { expect, test, type Page } from "@playwright/test";

test.skip(process.env.E2E_REAL_BACKEND === "1", "mock-mode flows");

async function open(page: Page, scenario = "happy") {
  await page.goto(`/?scenario=${scenario}`);
  await expect(page.getByRole("search")).toBeVisible();
}

async function search(page: Page, text = "chill flute") {
  await page.getByRole("textbox", { name: "Search by describing a sound" }).fill(text);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("list", { name: "Ranked results" })).toBeVisible();
}

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
