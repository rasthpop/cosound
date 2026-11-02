import { describe, expect, it } from "vitest";

import { componentTokens } from "./components";
import { DEFAULT_THEME, dark, light, themes } from "./semantic";
import type { SemanticTokens, ThemeName } from "./types";

// --- WCAG 2.x contrast ----------------------------------------------------------------------

type Rgba = [number, number, number, number];

function parse(color: string): Rgba {
  const hex = /^#([0-9a-f]{6})$/i.exec(color);
  if (hex?.[1]) {
    const n = parseInt(hex[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  const rgba = /^rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\)$/.exec(color);
  if (rgba) {
    const [, r, g, b, a] = rgba.map(Number) as [number, number, number, number, number];
    return [r, g, b, a];
  }
  throw new Error(`unsupported colour ${color}`);
}

/** `color` painted over an opaque `under`. */
function over(color: string, under: string): Rgba {
  const [r, g, b, a] = parse(color);
  const [ur, ug, ub, ua] = parse(under);
  if (ua !== 1) throw new Error(`backdrop ${under} must be opaque`);
  return [r * a + ur * (1 - a), g * a + ug * (1 - a), b * a + ub * (1 - a), 1];
}

function luminance([r, g, b]: Rgba): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(a: Rgba, b: Rgba): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const AA_TEXT = 4.5;
const AA_NON_TEXT = 3;

/**
 * Opaque pixels a glass panel can sit over on the map: the backdrop and every point fill at
 * full opacity (a dense cluster), genre hues included. Covers the darkest and the lightest map
 * pixel of a theme.
 */
function mapPixels(t: SemanticTokens): string[] {
  const p = t.color.map.point;
  return [t.color.map.backdrop, p.default, p.dimmed, p.other, ...t.color.map.categorical];
}

/** Opaque colours a panel or raised surface actually renders as, per backdrop. */
function panelSurfaces(t: SemanticTokens): Rgba[] {
  const { canvas, panel, raised } = t.color.surface;
  const backdrops = [canvas, ...mapPixels(t)];
  return backdrops.flatMap((under) => {
    const panelPixel = over(panel, under);
    const asHex = `rgba(${panelPixel.map((c) => Math.round(c)).slice(0, 3).join(", ")}, 1)`;
    return [panelPixel, over(raised, asHex)];
  });
}

/** Every (token, surface) pair below `minimum`, so one run reports all of them. */
function failures(colors: Record<string, string>, surfaces: Rgba[], minimum: number): string[] {
  return Object.entries(colors).flatMap(([name, color]) =>
    surfaces
      .map((surface) => [surface, contrast(parse(color), surface)] as const)
      .filter(([, ratio]) => ratio < minimum)
      .map(([s, ratio]) => `${name} ${color} on rgb(${s.slice(0, 3).map(Math.round).join(",")}): ${ratio.toFixed(2)}`),
  );
}

const THEMES = Object.entries(themes) as [ThemeName, SemanticTokens][];

describe.each(THEMES)("%s theme", (_name, t) => {
  const canvas = parse(t.color.surface.canvas);
  const surfaces = [canvas, ...panelSurfaces(t)];

  it("text meets AA on the canvas and on glass over the darkest and lightest map pixel", () => {
    expect(failures({ default: t.color.text.default, muted: t.color.text.muted }, surfaces, AA_TEXT)).toEqual([]);
  });

  it("the primary action's text meets AA on the accent", () => {
    expect(contrast(parse(t.color.text.onAccent), parse(t.color.accent.default))).toBeGreaterThanOrEqual(AA_TEXT);
  });

  it("focus ring and status, evidence, match and feedback marks meet 3:1 on every surface", () => {
    const c = t.color;
    const marks = {
      focus: c.focus.ring,
      accent: c.accent.default,
      ...c.state,
      ...c.evidence,
      ...c.match,
      ...c.feedback,
    };
    expect(failures(marks, surfaces, AA_NON_TEXT)).toEqual([]);
  });

  it("result and selection rings stand out from the map backdrop", () => {
    const backdrop = parse(t.color.map.backdrop);
    for (const ring of [t.color.map.point.result, t.color.map.point.selected, t.color.map.point.hover]) {
      expect(contrast(parse(ring), backdrop)).toBeGreaterThanOrEqual(AA_NON_TEXT);
    }
  });

  it("match bands are an ordered ramp: each band stands out clearly more than the one below", () => {
    const { strong, partial, weak } = t.color.match;
    const [w, p, s] = [weak, partial, strong].map((color) => contrast(parse(color), canvas)) as [
      number,
      number,
      number,
    ];
    expect(p / w).toBeGreaterThanOrEqual(1.2);
    expect(s / p).toBeGreaterThanOrEqual(1.2);
  });

  it("reduced motion has no pulse and no transition time", () => {
    const reduced = t.motion.reduced;
    expect(reduced.pulse).toBe(false);
    expect(Object.values(reduced.duration).every((ms) => ms === 0)).toBe(true);
    expect(t.motion.default.pulse).toBe(true);
  });

  it("component tokens resolve to this theme's semantic values", () => {
    const c = componentTokens(t);
    expect(c.panel.background).toBe(t.color.surface.panel);
    expect(c.button.primaryText).toBe(t.color.text.onAccent);
    expect(c.trackRow.height).toBe(t.density.comfortable.rowHeight);
  });
});

describe("token structure", () => {
  it("dark is the default and both themes define the same token paths", () => {
    expect(DEFAULT_THEME).toBe("dark");
    const paths = (o: object, prefix = ""): string[] =>
      Object.entries(o).flatMap(([k, v]) =>
        typeof v === "object" && v !== null ? paths(v as object, `${prefix}${k}.`) : [`${prefix}${k}`],
      );
    expect(paths(light)).toEqual(paths(dark));
  });

  it("encodes the plan's visual language (ui.md §2)", () => {
    expect(dark.color.surface.canvas).toBe("#0B0B0F");
    expect(dark.color.surface.panel).toBe("rgba(18, 18, 24, 0.72)");
    expect(dark.color.accent.default).toBe("#A78BFA");
    expect(dark.blur.panel).toBe(12);
    expect([dark.radius.md, dark.radius.lg]).toEqual([12, 16]);
    expect(Object.values(dark.font.size)).toEqual([13, 15, 20, 28]);
    expect(Object.values(dark.font.weight)).toEqual([400, 500]);
    expect(dark.density.comfortable.rowHeight).toBe(56);
    expect(dark.space.sm).toBe(8);
    expect(dark.opacity.point).toEqual({ default: 0.55, dimmed: 0.15, result: 1 });
    expect(dark.motion.default.duration).toMatchObject({ fast: 150, base: 250, camera: 600 });
  });

  it("every spacing step sits on the 4/8 px grid", () => {
    for (const px of Object.values(dark.space)) expect(px % 4).toBe(0);
  });
});
