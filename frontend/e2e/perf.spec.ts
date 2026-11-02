// Map performance probe (U05.T04), opt-in: numbers, not pass/fail gates. Results are written as
// test annotations and summarised in docs/ui/performance.md.
//   PERF=1 npx playwright test e2e/perf.spec.ts --reporter=list                  # synthetic 10k/100k
//   PERF=1 E2E_REAL_BACKEND=1 API_PROXY_TARGET=http://127.0.0.1:8000 npx playwright test e2e/perf.spec.ts
// Headless Chromium renders WebGL in software (SwiftShader), so frame rates are a lower bound.
import { expect, test, type Page } from "@playwright/test";

import { MAP_REGION } from "./helpers";

test.skip(process.env.PERF !== "1", "performance probe (PERF=1)");
test.use({ viewport: { width: 1280, height: 800 } });

const real = process.env.E2E_REAL_BACKEND === "1";
// frame rates are only measured up to 10k: beyond that, software WebGL makes them meaningless
const DATASETS = real
  ? [{ name: "fma_small (real backend)", query: "", frames: true }]
  : [
      { name: "10k synthetic", query: "?mapPoints=10000", frames: true },
      { name: "100k synthetic", query: "?mapPoints=100000", frames: false },
    ];

/** Frames painted while `action` runs, as frames per second. */
async function fps(page: Page, action: () => Promise<void>): Promise<number> {
  await page.evaluate(() => {
    const w = window as unknown as { __frames: number; __counting: boolean };
    w.__frames = 0;
    w.__counting = true;
    const tick = () => {
      if (!w.__counting) return;
      w.__frames += 1;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  const start = Date.now();
  await action();
  const seconds = (Date.now() - start) / 1000;
  const frames = await page.evaluate(() => {
    const w = window as unknown as { __frames: number; __counting: boolean };
    w.__counting = false;
    return w.__frames;
  });
  return frames / seconds;
}

/** ms from `action` until two frames have been painted after it (the change is on screen). */
async function paintLatency(
  page: Page,
  action: () => Promise<void>,
): Promise<number> {
  const start = await page.evaluate(() => performance.now());
  await action();
  return page.evaluate(
    (t0) =>
      new Promise<number>((resolve) =>
        requestAnimationFrame(() =>
          requestAnimationFrame(() => resolve(performance.now() - t0)),
        ),
      ),
    start,
  );
}

for (const { name, query, frames } of DATASETS) {
  test(name, async ({ page }) => {
    test.setTimeout(420_000);
    const note = (label: string, value: string) =>
      test
        .info()
        .annotations.push({ type: label, description: `${name}: ${value}` });

    const t0 = Date.now();
    await page.goto(`/${query}`);
    const map = page.getByRole("region", { name: MAP_REGION });
    // page-in: until the point count stops growing
    let count = -1;
    for (;;) {
      await page.waitForTimeout(250);
      const text = (await map.textContent({ timeout: 60_000 })) ?? "";
      const n = Number(/Map of (\d+) tracks/.exec(text)?.[1] ?? -1);
      if (n > 0 && n === count) break;
      count = n;
      if (Date.now() - t0 > 180_000) break;
    }
    note("points", String(count));
    note("page-in", `${((Date.now() - t0) / 1000).toFixed(1)} s to all points`);

    const box = (await map.boundingBox())!;
    const cx = box.x + box.width / 2;
    const cy = box.y + box.height / 2;

    if (frames) {
      const pan = await fps(page, async () => {
        await page.mouse.move(cx, cy);
        await page.mouse.down();
        for (let i = 0; i < 60; i++)
          await page.mouse.move(
            cx + Math.sin(i / 6) * 200,
            cy + Math.cos(i / 6) * 120,
            { steps: 2 },
          );
        await page.mouse.up();
      });
      note("pan", `${pan.toFixed(0)} fps`);

      const zoom = await fps(page, async () => {
        await page.mouse.move(cx, cy);
        for (let i = 0; i < 30; i++) {
          await page.mouse.wheel(0, i < 15 ? -120 : 120);
          await page.waitForTimeout(16);
        }
      });
      note("zoom", `${zoom.toFixed(0)} fps`);
    }

    // a selection restyles every point (update triggers): open the list alternative and pick one
    await page.getByRole("button", { name: "Reset view" }).click();
    await page.getByRole("button", { name: "List of map tracks" }).click();
    const item = page
      .getByRole("region", { name: "Tracks on the map" })
      .getByRole("listitem")
      .nth(3)
      .getByRole("button");
    const select = await paintLatency(page, () => item.click());
    note("selection restyle", `${select.toFixed(0)} ms to paint`);

    if (real) {
      // search → results highlighted on the real map
      const input = page.getByRole("textbox", {
        name: "Search by describing a sound",
      });
      await input.fill("something chill with a flute");
      const start = Date.now();
      await page.keyboard.press("Enter");
      await expect(map).toContainText("results highlighted", {
        timeout: 120_000,
      });
      note(
        "search → highlight",
        `${Date.now() - start} ms (includes the backend search)`,
      );
    }
  });
}
