// Shared helpers for the mock-mode E2E specs.
import { readFileSync } from "node:fs";

import { expect, type Page } from "@playwright/test";

import { fitBounds, type Bounds } from "../src/components/map/fitBounds";

export const fixtureJson = <T>(name: string): T =>
  JSON.parse(readFileSync(new URL(`../src/mocks/fixtures/${name}.json`, import.meta.url), "utf8")) as T;

const mapMeta = fixtureJson<{ bounds: Bounds }>("map_meta");
const mapPoints = [
  ...fixtureJson<{ points: { track_id: string; x: number; y: number }[] }>("map_points_page1").points,
  ...fixtureJson<{ points: { track_id: string; x: number; y: number }[] }>("map_points_page2").points,
];

export const MAP_REGION = "Map of tracks arranged by audio similarity (approximate)";

export async function open(page: Page, scenario = "happy") {
  await page.goto(`/?scenario=${scenario}`);
  await expect(page.getByRole("search")).toBeVisible();
}

export const searchInput = (page: Page) => page.getByRole("textbox", { name: "Search by describing a sound" });

export async function search(page: Page, text = "chill flute") {
  await searchInput(page).fill(text);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("list", { name: "Ranked results" })).toBeVisible();
}

/**
 * Where a fixture point is drawn while the camera shows the whole projection (the first view, or
 * after "Reset view"). With reduced motion the camera moves instantly, so this is exact.
 */
export function screenPosition(page: Page, trackId: string) {
  const size = page.viewportSize()!;
  const { target, zoom } = fitBounds(mapMeta.bounds, size);
  const p = mapPoints.find((q) => q.track_id === trackId)!;
  const scale = 2 ** zoom;
  // OrthographicView with flipY: false — y grows upwards
  return { x: size.width / 2 + (p.x - target[0]!) * scale, y: size.height / 2 - (p.y - target[1]!) * scale };
}
