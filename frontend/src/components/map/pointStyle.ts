// Per-point styles for the map, from the theme's point states and genre scale (theme/scales).
// The map passes these accessors to deck.gl; it never parses CSS.
import type { GenreScale } from "@/theme/scales/categorical";
import { pointStateOf, pointStyle, type PointStyle } from "@/theme/scales/pointStates";
import type { MotionSet, SemanticTokens } from "@/theme/tokens/types";

export interface StyleContext {
  selected: ReadonlySet<string>;
  highlighted: ReadonlySet<string>;
  hovered: string | null;
  dimUnhighlighted: boolean;
  scale: Pick<GenreScale, "colorOf">;
  tokens: SemanticTokens;
  motion: MotionSet;
}

export interface StyledPoint {
  track_id: string;
  genre: string | null;
}

export function styleFor(point: StyledPoint, ctx: StyleContext): PointStyle {
  const state = pointStateOf({
    selected: ctx.selected.has(point.track_id),
    hovered: ctx.hovered === point.track_id,
    highlighted: ctx.highlighted.has(point.track_id),
    dimUnhighlighted: ctx.dimUnhighlighted && ctx.highlighted.size > 0,
  });
  return pointStyle(state, ctx.scale.colorOf(point.genre), ctx.tokens, ctx.motion);
}

/** deck.gl accessors over `styleFor`, one style computation per point and accessor call. */
export function accessors(ctx: StyleContext) {
  return {
    getFillColor: (p: StyledPoint) => styleFor(p, ctx).fill,
    getRadius: (p: StyledPoint) => styleFor(p, ctx).radius,
    getLineColor: (p: StyledPoint) => styleFor(p, ctx).line,
    getLineWidth: (p: StyledPoint) => styleFor(p, ctx).lineWidth,
  };
}
