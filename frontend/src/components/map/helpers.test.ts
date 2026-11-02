import { describe, expect, it } from "vitest";

import { genreScale } from "@/theme/scales/categorical";
import { toRgba } from "@/theme/scales/toRgba";
import { dark, light } from "@/theme/tokens/semantic";

import { cameraTransition, easeOut } from "./camera";
import { boundsOf, clampZoom, fitBounds, FIT_PADDING, zoomRange } from "./fitBounds";
import { setKey, triggerKeys } from "./keys";
import { styleFor, type StyleContext } from "./pointStyle";

const VIEW = { width: 1000, height: 800 };

describe("fitBounds", () => {
  it("has no bounds for no points and skips non-finite coordinates", () => {
    expect(boundsOf([])).toBeNull();
    expect(boundsOf([{ x: Number.NaN, y: 1 }])).toBeNull();
    expect(boundsOf([{ x: 1, y: 2 }, { x: -1, y: Number.POSITIVE_INFINITY }])).toEqual({ min_x: 1, max_x: 1, min_y: 2, max_y: 2 });
  });

  it("centres a subset and fits it inside the padded viewport", () => {
    const b = boundsOf([{ x: -1, y: 0 }, { x: 3, y: 2 }])!;
    const cam = fitBounds(b, VIEW);
    expect(cam.target).toEqual([1, 1, 0]);
    const scale = 2 ** cam.zoom;
    expect(4 * scale).toBeLessThanOrEqual(VIEW.width - 2 * FIT_PADDING + 1e-9);
    expect(2 * scale).toBeLessThanOrEqual(VIEW.height - 2 * FIT_PADDING + 1e-9);
    // the limiting side touches the padding
    expect(Math.max(4 * scale - (VIEW.width - 2 * FIT_PADDING), 2 * scale - (VIEW.height - 2 * FIT_PADDING))).toBeCloseTo(0);
  });

  it("gives a single point a finite zoom centred on it", () => {
    const cam = fitBounds(boundsOf([{ x: 0.3, y: -0.2 }])!, VIEW);
    expect(cam.target).toEqual([0.3, -0.2, 0]);
    expect(Number.isFinite(cam.zoom)).toBe(true);
  });

  it("clamps zoom to the projection's range", () => {
    const projection = { min_x: -1, max_x: 1, min_y: -1, max_y: 1 };
    const range = zoomRange(projection, VIEW);
    expect(range.maxZoom).toBeGreaterThan(range.minZoom);
    expect(clampZoom({ target: [0, 0, 0], zoom: -100 }, range).zoom).toBe(range.minZoom);
    expect(clampZoom({ target: [0, 0, 0], zoom: 100 }, range).zoom).toBe(range.maxZoom);
    const inside = (range.minZoom + range.maxZoom) / 2;
    expect(clampZoom({ target: [0, 0, 0], zoom: inside }, range).zoom).toBe(inside);
  });
});

describe("camera", () => {
  it("flies in 600 ms, and instantly under reduced motion", () => {
    expect(cameraTransition(dark.motion.default).transitionDuration).toBe(600);
    expect(cameraTransition(dark.motion.reduced).transitionDuration).toBe(0);
  });

  it("eases out from 0 to 1", () => {
    expect(easeOut(0)).toBe(0);
    expect(easeOut(1)).toBe(1);
    expect(easeOut(0.5)).toBeGreaterThan(0.5);
  });
});

describe("keys", () => {
  it("are stable across Set identity and order, and change with content", () => {
    expect(setKey(new Set(["b", "a"]))).toBe(setKey(["a", "b"]));
    expect(setKey(["a", "b"])).not.toBe(setKey(["a", "c"]));
    expect(setKey([])).toBe("");
    expect(setKey(null)).toBe("");
  });

  it("separate state from theme", () => {
    const base = { selected: ["a"], highlighted: ["b", "c"], hovered: null, themeKey: "dark" };
    const k1 = triggerKeys(base);
    expect(triggerKeys({ ...base, highlighted: new Set(["c", "b"]) })).toEqual(k1);
    expect(triggerKeys({ ...base, selected: ["z"] }).getRadius).not.toBe(k1.getRadius);
    const themed = triggerKeys({ ...base, themeKey: "light" });
    expect(themed.getFillColor).not.toBe(k1.getFillColor);
    expect(themed.getRadius).toBe(k1.getRadius);
  });
});

describe("pointStyle", () => {
  const scale = genreScale([{ genre: "Folk", count: 2 }, { genre: "Rock", count: 1 }], dark);
  const ctx = (over: Partial<StyleContext> = {}): StyleContext => ({
    selected: new Set(),
    highlighted: new Set(),
    hovered: null,
    dimUnhighlighted: false,
    scale,
    tokens: dark,
    motion: dark.motion.default,
    ...over,
  });

  it("colours by genre and dims non-results only while results exist", () => {
    const folk = { track_id: "t1", genre: "Folk" };
    expect(styleFor(folk, ctx()).fill).toEqual(toRgba(scale.colorOf("Folk"), dark.opacity.point.default));
    expect(styleFor(folk, ctx({ dimUnhighlighted: true })).fill[3]).toBe(toRgba("#000000", dark.opacity.point.default)[3]);
    const dimmed = styleFor(folk, ctx({ dimUnhighlighted: true, highlighted: new Set(["t2"]) }));
    expect(dimmed.fill[3]).toBe(toRgba("#000000", dark.opacity.point.dimmed)[3]);
  });

  it("selection beats hover beats result, and is more than colour", () => {
    const p = { track_id: "t1", genre: null };
    const result = styleFor(p, ctx({ highlighted: new Set(["t1"]) }));
    const selected = styleFor(p, ctx({ highlighted: new Set(["t1"]), selected: new Set(["t1"]), hovered: "t1" }));
    expect(selected.radius).toBeGreaterThan(result.radius);
    expect(selected.lineWidth).toBeGreaterThan(result.lineWidth);
    expect(selected.fill).toEqual(result.fill);
    expect(result.fill.slice(0, 3)).toEqual(toRgba(dark.color.map.point.default).slice(0, 3)); // null genre → neutral
  });

  it("follows the theme", () => {
    const lightScale = genreScale([{ genre: "Folk", count: 1 }], light);
    const s = styleFor({ track_id: "t", genre: "Folk" }, ctx({ tokens: light, scale: lightScale }));
    expect(s.fill.slice(0, 3)).toEqual(toRgba(light.color.map.categorical[0]).slice(0, 3));
  });
});
