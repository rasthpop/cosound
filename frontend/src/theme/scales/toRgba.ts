// Token colours as deck.gl tuples. deck.gl code never parses CSS; it calls this helper with
// colours from the theme tokens.
import type { Color } from "../tokens/types";

/** `[r, g, b, a]`, each 0-255, the format deck.gl accessors return. */
export type RGBA = [number, number, number, number];

const HEX = /^#([0-9a-f]{6})$/i;
const RGBA_FN = /^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*([\d.]+)\s*)?\)$/i;

/**
 * Convert a token colour (`#rrggbb`, `rgb(...)` or `rgba(...)`) to a deck.gl tuple.
 * `opacity` (0-1) multiplies the colour's own alpha.
 */
export function toRgba(color: Color, opacity = 1): RGBA {
  if (opacity < 0 || opacity > 1) throw new RangeError(`opacity must be within [0, 1], got ${opacity}`);
  const hex = HEX.exec(color);
  if (hex?.[1]) {
    const n = parseInt(hex[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, Math.round(255 * opacity)];
  }
  const fn = RGBA_FN.exec(color);
  if (fn) {
    const [r, g, b] = [fn[1], fn[2], fn[3]].map(Number) as [number, number, number];
    const alpha = fn[4] === undefined ? 1 : Number(fn[4]);
    if ([r, g, b].some((c) => c > 255) || alpha > 1) throw new RangeError(`colour out of range: ${color}`);
    return [r, g, b, Math.round(255 * alpha * opacity)];
  }
  throw new TypeError(`unsupported colour ${JSON.stringify(color)}; tokens use #rrggbb or rgba()`);
}

/** Fully transparent: "no ring". */
export const TRANSPARENT: RGBA = [0, 0, 0, 0];
