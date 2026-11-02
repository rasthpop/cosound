// Map point states (ui.md §2 "Map points" / "Highlight"), as deck.gl-ready styles.
// Selection is never colour alone: selected points are larger, ringed in the accent and pulse
// (no pulse under reduced motion); results are larger with a thin light ring.
import type { Color, MotionSet, SemanticTokens } from "../tokens/types";
import { TRANSPARENT, toRgba, type RGBA } from "./toRgba";

export type PointState = "default" | "dimmed" | "result" | "hovered" | "selected";

export interface PointFlags {
  selected?: boolean;
  hovered?: boolean;
  /** In the current search results. */
  highlighted?: boolean;
  /** Results are on screen, so points that are not results recede. */
  dimUnhighlighted?: boolean;
}

/** Precedence: selected > hovered > result > dimmed > default. */
export function pointStateOf(flags: PointFlags): PointState {
  if (flags.selected) return "selected";
  if (flags.hovered) return "hovered";
  if (flags.highlighted) return "result";
  if (flags.dimUnhighlighted) return "dimmed";
  return "default";
}

export interface PointStyle {
  fill: RGBA;
  /** Radius in CSS px (`radiusUnits: "pixels"`). */
  radius: number;
  line: RGBA;
  /** Ring width in CSS px (`lineWidthUnits: "pixels"`); 0 = no ring. */
  lineWidth: number;
  /** Whether the renderer may animate a pulse on this point. */
  pulse: boolean;
}

/** The style of a point in `state`, filled with its genre colour `fill`. */
export function pointStyle(state: PointState, fill: Color, tokens: SemanticTokens, motion: MotionSet): PointStyle {
  const { opacity, size } = tokens;
  const ring = tokens.color.map.point;
  switch (state) {
    case "default":
      return { fill: toRgba(fill, opacity.point.default), radius: size.point.default, line: TRANSPARENT, lineWidth: 0, pulse: false };
    case "dimmed":
      return { fill: toRgba(fill, opacity.point.dimmed), radius: size.point.default, line: TRANSPARENT, lineWidth: 0, pulse: false };
    case "result":
      return {
        fill: toRgba(fill, opacity.point.result),
        radius: size.point.result,
        line: toRgba(ring.result),
        lineWidth: size.ring.result,
        pulse: false,
      };
    case "hovered":
      return {
        fill: toRgba(fill, opacity.point.result),
        radius: Math.max(size.point.hover, size.point.result),
        line: toRgba(ring.hover),
        lineWidth: size.ring.result,
        pulse: false,
      };
    case "selected":
      return {
        fill: toRgba(fill, opacity.point.result),
        radius: size.point.selected,
        line: toRgba(ring.selected),
        lineWidth: size.ring.selected,
        pulse: motion.pulse,
      };
  }
}
