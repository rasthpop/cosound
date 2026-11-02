// Accessibility audit of the Discover screen in mock mode (U05.T01, ui.md §7). See
// docs/ui/accessibility.md for what is checked where.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

import { themes } from "../src/theme/tokens/semantic";

test.skip(process.env.E2E_REAL_BACKEND === "1", "mock-mode audit");

const SCENARIOS = [
  "happy",
  "degraded-semantic",
  "map-down",
  "no-confident-match",
  "needs-clarification",
  "slow-network",
  "errors",
  "empty",
  "llm-fallback",
  "offline",
] as const;
const VIEWPORTS = {
  desktop: { width: 1280, height: 800 },
  mobile: { width: 390, height: 844 },
} as const;
const SCHEMES = ["dark", "light"] as const;

const input = (page: Page) =>
  page.getByRole("textbox", { name: "Search by describing a sound" });
const live = (page: Page) =>
  page.locator('[aria-live="polite"][aria-atomic="true"]');

/** Serious and critical WCAG 2.1 A/AA violations, as "rule: target" lines. */
async function violations(page: Page): Promise<string[]> {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return result.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .flatMap((v) => v.nodes.map((n) => `${v.id}: ${n.target.join(" ")}`));
}

/** Tab forward until `target` has focus; fails after `max` presses. */
async function tabTo(page: Page, target: Locator, max = 40) {
  for (let i = 0; i < max; i++) {
    if (
      await target
        .evaluate((el) => el === document.activeElement)
        .catch(() => false)
    )
      return;
    await page.keyboard.press("Tab");
  }
  await expect(target).toBeFocused();
}

// ── axe on every scenario, both viewports and both themes ──
for (const scheme of SCHEMES) {
  for (const [viewportName, viewport] of Object.entries(VIEWPORTS)) {
    test.describe(`axe · ${scheme} · ${viewportName}`, () => {
      test.use({ colorScheme: scheme, viewport, reducedMotion: "reduce" });
      for (const scenario of SCENARIOS) {
        test(scenario, async ({ page }) => {
          await page.goto(`/?scenario=${scenario}`);
          await expect(page.getByRole("search")).toBeVisible();
          expect(await violations(page), "idle").toEqual([]);

          await input(page).fill("chill flute");
          await page.keyboard.press("Enter");
          // every scenario settles into a state the live region or an alert reports
          await expect(
            page
              .getByRole("alert")
              .or(
                live(page)
                  .filter({ hasText: /\S/ })
                  .filter({ hasNotText: "Searching…" }),
              ),
          )
            .toBeVisible({ timeout: 10_000 })
            .catch(() => {});
          await expect(
            page.getByRole("progressbar", { name: "Searching" }),
          ).toHaveCount(0, { timeout: 10_000 });
          expect(await violations(page), "after search").toEqual([]);

          if (scenario === "happy") {
            await page
              .getByRole("list", { name: "Ranked results" })
              .getByRole("button", { name: "Example Track 1", exact: true })
              .click();
            await expect(
              page
                .getByRole("dialog")
                .getByRole("region", { name: /nearby|sound/i }),
            ).toBeVisible();
            expect(await violations(page), "details open").toEqual([]);
          }
        });
      }
    });
  }
}

// ── the keyboard path of ui.md §7 ──
test.describe("keyboard-only walkthrough", () => {
  test.use({ reducedMotion: "reduce", viewport: VIEWPORTS.desktop });

  test("/ → input → results → feedback → details (focus loop & return) → map list alternative", async ({
    page,
  }) => {
    await page.goto("/?scenario=happy");
    await expect(input(page)).toBeFocused(); // flow 1: focused on arrival
    await page.keyboard.press("Escape");
    await expect(input(page)).not.toBeFocused();
    await page.keyboard.press("/");
    await expect(input(page)).toBeFocused();

    await page.keyboard.type("chill flute");
    await page.keyboard.press("Enter");
    await expect(live(page)).toHaveText(
      "3 results for “Something chill with a flute”",
    );

    const rows = page.getByRole("list", { name: "Ranked results" });
    const title = rows.getByRole("button", {
      name: "Example Track 1",
      exact: true,
    });
    await tabTo(page, title);

    // feedback is reachable by Tab (revealed on focus, not only on hover)
    const less = rows.getByRole("button", {
      name: "Less like this: Example Track 1",
    });
    await tabTo(page, less);
    await expect(less).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("region", { name: "What changed" }),
    ).toBeVisible();
    await expect(live(page)).toContainText("Results refined.");

    // details: opens on Enter, Tab stays inside, Esc closes and focus returns to the row
    await title.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Example Track 1" }),
    ).toBeVisible();
    await expect
      .poll(() => dialog.evaluate((d) => d.contains(document.activeElement)))
      .toBe(true);
    for (let i = 0; i < 25; i++) {
      await page.keyboard.press("Tab");
      expect(
        await dialog.evaluate((d) => d.contains(document.activeElement)),
        `Tab ${i + 1} left the drawer`,
      ).toBe(true);
    }
    await page.keyboard.press("Shift+Tab");
    expect(
      await dialog.evaluate((d) => d.contains(document.activeElement)),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(title).toBeFocused();

    // the map's list alternative, from the map controls
    const listToggle = page.getByRole("button", { name: "List of map tracks" });
    await tabTo(page, listToggle);
    await page.keyboard.press("Enter");
    const alt = page.getByRole("region", { name: "Tracks on the map" });
    const second = alt.getByRole("button", { name: /Example Track 2/ });
    await tabTo(page, second);
    await page.keyboard.press("Enter");
    await expect(second).toHaveAttribute("aria-current", "true");
    await expect(dialog).toBeVisible(); // selecting from the list opens details too
  });
});

// ── text contrast on glass panels over the densest map area ──
// The map is drawn with WebGL, so axe can't see under the panels. This measures it: hide the
// floating UI, screenshot the canvas with 10k points, blur it like the panels' backdrop filter, and
// take the most extreme pixel (brightest on dark, where additive dots glow; darkest on light). The
// panel's translucent fill over that pixel is the worst background any panel text gets.
type Rgb = [number, number, number];
const parse = (c: string): [number, number, number, number] => {
  const hex = /^#([0-9a-f]{6})$/i.exec(c);
  if (hex?.[1]) {
    const n = parseInt(hex[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  const m = /^rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\)$/.exec(c)!;
  return [Number(m[1]), Number(m[2]), Number(m[3]), Number(m[4])];
};
const lum = ([r, g, b]: Rgb) => {
  const lin = (v: number) =>
    (v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
};
const contrast = (a: Rgb, b: Rgb) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
};

for (const scheme of SCHEMES) {
  test.describe(`contrast · ${scheme}`, () => {
    test.use({
      colorScheme: scheme,
      viewport: VIEWPORTS.desktop,
      reducedMotion: "reduce",
    });
    test("panel text keeps AA contrast over the densest map area", async ({
      page,
    }) => {
      await page.goto("/?mapPoints=10000");
      await expect(
        page.getByRole("region", { name: "Map of tracks by audio similarity" }),
      ).toContainText("Map of 10000 tracks", { timeout: 30_000 });
      await page.waitForTimeout(800); // points fade in
      await page.addStyleTag({
        content:
          'main[aria-label="Discover music"] { visibility: hidden !important; }',
      });
      const shot = (await page.screenshot()).toString("base64");

      const extreme = await page.evaluate(
        async ({ png, brightest }) => {
          const img = new Image();
          img.src = `data:image/png;base64,${png}`;
          await img.decode();
          const canvas = document.createElement("canvas");
          canvas.width = img.width;
          canvas.height = img.height;
          const ctx = canvas.getContext("2d")!;
          ctx.filter = "blur(12px)"; // the panels' backdrop blur (theme blur.panel)
          ctx.drawImage(img, 0, 0);
          const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
          let best: [number, number, number] = [data[0]!, data[1]!, data[2]!];
          let bestY = brightest ? -1 : 1e9;
          for (let i = 0; i < data.length; i += 4) {
            const y =
              0.2126 * data[i]! + 0.7152 * data[i + 1]! + 0.0722 * data[i + 2]!;
            if (brightest ? y > bestY : y < bestY) {
              bestY = y;
              best = [data[i]!, data[i + 1]!, data[i + 2]!];
            }
          }
          return best;
        },
        { png: shot, brightest: scheme === "dark" },
      );

      const t = themes[scheme];
      const [pr, pg, pb, pa] = parse(t.color.surface.panel);
      const panel: Rgb = [
        pr * pa + extreme[0] * (1 - pa),
        pg * pa + extreme[1] * (1 - pa),
        pb * pa + extreme[2] * (1 - pa),
      ];
      for (const [name, color] of [
        ["text", t.color.text.default],
        ["muted text", t.color.text.muted],
      ] as const) {
        const ratio = contrast(parse(color).slice(0, 3) as Rgb, panel);
        test
          .info()
          .annotations.push({
            type: "contrast",
            description: `${scheme} ${name}: ${ratio.toFixed(2)} over panel on rgb(${extreme.join(",")})`,
          });
        expect(
          ratio,
          `${name} on glass over rgb(${extreme.join(",")})`,
        ).toBeGreaterThanOrEqual(4.5);
      }
    });
  });
}
