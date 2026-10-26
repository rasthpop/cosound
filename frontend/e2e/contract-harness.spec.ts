// M6 acceptance (P09.T09): search → plate → feedback → refreshed plate → map points, through
// the four hooks only, with no ML or retrieval logic in the frontend.
import { expect, test, type Page } from "@playwright/test";

const realBackend = process.env.E2E_REAL_BACKEND === "1";

async function open(page: Page, scenario?: string) {
  await page.goto(`/__dev/harness${scenario ? `?scenario=${scenario}` : ""}`);
  await expect(page.getByRole("heading", { name: /contract harness/i })).toBeVisible();
}

test.describe("mock backend", () => {
  test.skip(realBackend, "mock-mode flow");

  test("search, feedback, refreshed plate, details and map points", async ({ page }) => {
    await open(page, "happy");

    await page.getByRole("button", { name: "search", exact: true }).click();
    await expect(page.getByTestId("search-status")).toHaveText("success");
    await expect(page.getByTestId("outcome")).toHaveText("ok");
    await expect(page.getByTestId("plate-item")).toHaveCount(3);
    const session = await page.getByTestId("session-id").textContent();
    await expect(page.getByTestId("query-id")).toHaveText("qry_mock_1");

    const first = page.getByTestId("plate-item").first();
    await first.getByRole("button", { name: "NOT_RELEVANT" }).click();
    await expect(page.getByTestId("feedback-accepted")).toHaveText("true");
    await expect(page.getByTestId("next-action")).toHaveText("REFINE_SEARCH");
    await expect(page.getByTestId("query-id")).toHaveText("qry_mock_2"); // refreshed plate shown
    await expect(page.getByTestId("session-id")).toHaveText(session ?? "");
    await expect(page.getByTestId("change-summary")).not.toHaveText("none");

    await page.getByTestId("plate-item").first().getByRole("button", { name: "SELECT_TRACK" }).click();
    await expect(page.getByTestId("details-status")).toContainText("success");
    await expect(page.getByTestId("neighbors")).toContainText("clap_cosine");

    await page.getByLabel("free text").fill("lovely weather");
    await page.getByRole("button", { name: "send text" }).click();
    await expect(page.getByTestId("feedback-accepted")).toHaveText("false");

    await expect(page.getByTestId("map-availability")).toHaveText("available");
    await expect(page.getByTestId("map-count")).toHaveText("3");
    await page.getByRole("button", { name: "load more" }).click();
    await expect(page.getByTestId("map-count")).toHaveText("5");
    await expect(page.getByRole("button", { name: "load more" })).toBeDisabled();
  });

  test("map down: the map says unavailable and search still works", async ({ page }) => {
    await open(page, "map-down");
    await expect(page.getByTestId("map-availability")).toHaveText("unavailable");
    await page.getByRole("button", { name: "search", exact: true }).click();
    await expect(page.getByTestId("outcome")).toHaveText("ok");
    await expect(page.getByTestId("warnings")).toContainText("map_unavailable");
  });

  test("degraded semantic search is reported, not hidden", async ({ page }) => {
    await open(page, "degraded-semantic");
    await page.getByRole("button", { name: "search", exact: true }).click();
    await expect(page.getByTestId("warnings")).toHaveText("semantic_unavailable");
    await expect(page.getByTestId("capabilities")).toContainText('"semantic":"unavailable"');
  });
});

test.describe("real backend", () => {
  test.skip(!realBackend, "set E2E_REAL_BACKEND=1 and API_PROXY_TARGET with the API running");

  test("search → feedback → refreshed plate → map points", async ({ page }) => {
    await open(page);
    await page.getByRole("button", { name: "search", exact: true }).click();
    await expect(page.getByTestId("search-status")).toHaveText("success", { timeout: 90_000 });
    await expect(page.getByTestId("outcome")).toHaveText("ok");
    const items = page.getByTestId("plate-item");
    await expect(items.first()).toBeVisible();
    const removed = await items.first().getAttribute("data-track-id");
    const firstQuery = await page.getByTestId("query-id").textContent();

    await items.first().getByRole("button", { name: "NOT_RELEVANT" }).click();
    await expect(page.getByTestId("feedback-accepted")).toHaveText("true", { timeout: 60_000 });
    await expect(page.getByTestId("query-id")).not.toHaveText(firstQuery ?? "");
    await expect(page.locator(`[data-testid=plate-item][data-track-id="${removed}"]`)).toHaveCount(0);

    await expect(page.getByTestId("map-availability")).toHaveText("available");
    await expect(page.getByTestId("map-count")).toHaveText("3");
    await page.getByRole("button", { name: "load more" }).click();
    await expect(page.getByTestId("map-count")).toHaveText("6");
  });
});
