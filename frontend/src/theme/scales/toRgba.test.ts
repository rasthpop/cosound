import { describe, expect, it } from "vitest";

import { dark, light } from "../tokens/semantic";
import { toRgba } from "./toRgba";

describe("toRgba", () => {
  it("converts hex colours to 0-255 tuples", () => {
    expect(toRgba("#0B0B0F")).toEqual([11, 11, 15, 255]);
    expect(toRgba("#a78bfa")).toEqual([167, 139, 250, 255]);
  });

  it("applies opacity on top of the colour's own alpha", () => {
    expect(toRgba("#FFFFFF", 0.55)).toEqual([255, 255, 255, 140]);
    expect(toRgba("rgba(18, 18, 24, 0.72)")).toEqual([18, 18, 24, 184]);
    expect(toRgba("rgba(18, 18, 24, 0.5)", 0.5)).toEqual([18, 18, 24, 64]);
    expect(toRgba("rgb(1, 2, 3)")).toEqual([1, 2, 3, 255]);
  });

  it("rejects colours it cannot read instead of guessing", () => {
    expect(() => toRgba("red")).toThrow(TypeError);
    expect(() => toRgba("#fff")).toThrow(TypeError);
    expect(() => toRgba("rgb(300, 0, 0)")).toThrow(RangeError);
    expect(() => toRgba("#000000", 2)).toThrow(RangeError);
  });

  it("reads every map colour token of both themes", () => {
    for (const t of [dark, light]) {
      const { point, categorical, backdrop } = t.color.map;
      for (const c of [backdrop, ...Object.values(point), ...categorical, t.color.accent.default]) {
        const rgba = toRgba(c);
        expect(rgba).toHaveLength(4);
        expect(rgba.every((v) => Number.isInteger(v) && v >= 0 && v <= 255)).toBe(true);
      }
    }
  });
});
