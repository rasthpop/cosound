import { describe, expect, it } from "vitest";

import { dark } from "../tokens/semantic";
import { pointStateOf, pointStyle, type PointState } from "./pointStates";
import { toRgba, TRANSPARENT } from "./toRgba";

const BLUE = dark.color.map.categorical[0];
const style = (state: PointState, motion = dark.motion.default) => pointStyle(state, BLUE, dark, motion);

describe("pointStateOf", () => {
  it("applies the precedence selected > hovered > result > dimmed > default", () => {
    expect(pointStateOf({ selected: true, hovered: true, highlighted: true })).toBe("selected");
    expect(pointStateOf({ hovered: true, highlighted: true })).toBe("hovered");
    expect(pointStateOf({ highlighted: true, dimUnhighlighted: true })).toBe("result");
    expect(pointStateOf({ dimUnhighlighted: true })).toBe("dimmed");
    expect(pointStateOf({})).toBe("default");
  });
});

describe("pointStyle", () => {
  it("default points are small soft dots at the plan's opacity (ui.md §2)", () => {
    const s = style("default");
    expect(s.fill).toEqual(toRgba(BLUE, 0.55));
    expect(s.radius * 2).toBeGreaterThanOrEqual(2);
    expect(s.radius * 2).toBeLessThanOrEqual(4);
    expect(s.line).toEqual(TRANSPARENT);
  });

  it("dimmed points keep their colour at low opacity", () => {
    expect(style("dimmed").fill).toEqual(toRgba(BLUE, 0.15));
  });

  it("results are full opacity, 6-8 px, with a thin light ring", () => {
    const s = style("result");
    expect(s.fill[3]).toBe(255);
    expect(s.radius * 2).toBeGreaterThanOrEqual(6);
    expect(s.radius * 2).toBeLessThanOrEqual(8);
    expect(s.line).toEqual(toRgba(dark.color.map.point.result));
    expect(s.lineWidth).toBe(1);
  });

  it("selection differs by size and ring width, not by colour alone, and pulses", () => {
    const selected = style("selected");
    const result = style("result");
    expect(selected.fill).toEqual(result.fill); // same genre fill
    expect(selected.radius).toBeGreaterThan(result.radius);
    expect(selected.lineWidth).toBeGreaterThan(result.lineWidth);
    expect(selected.line).toEqual(toRgba(dark.color.accent.default));
    expect(selected.pulse).toBe(true);
  });

  it("no pulse under reduced motion", () => {
    expect(style("selected", dark.motion.reduced).pulse).toBe(false);
  });

  it("hover adds a ring and never shrinks a result", () => {
    const hovered = style("hovered");
    expect(hovered.lineWidth).toBeGreaterThan(0);
    expect(hovered.radius).toBeGreaterThanOrEqual(style("result").radius);
  });
});
