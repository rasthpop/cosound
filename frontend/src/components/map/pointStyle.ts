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

function stateOf(point: StyledPoint, ctx: StyleContext) {
  return pointStateOf({
    selected: ctx.selected.has(point.track_id),
    hovered: ctx.hovered === point.track_id,
    highlighted: ctx.highlighted.has(point.track_id),
    dimUnhighlighted: ctx.dimUnhighlighted && ctx.highlighted.size > 0,
  });
}

export function styleFor(point: StyledPoint, ctx: StyleContext): PointStyle {
  return pointStyle(stateOf(point, ctx), ctx.scale.colorOf(point.genre), ctx.tokens, ctx.motion);
}

/**
 * deck.gl accessors over `styleFor`. A point's style depends only on its state and genre colour,
 * so the few distinct styles are computed once per accessor set and shared (deck.gl copies the
 * values into its buffers), and each point's state is worked out once for all four accessors.
 */
export function accessors(ctx: StyleContext) {
  const cache = new Map<string, PointStyle>();
  // deck.gl calls the four accessors per point; the first call's result serves the other three
  const perPoint = new WeakMap<StyledPoint, PointStyle>();
  const style = (p: StyledPoint): PointStyle => {
    const known = perPoint.get(p);
    if (known) return known;
    const state = stateOf(p, ctx);
    const color = ctx.scale.colorOf(p.genre);
    const key = `${state}|${color}`;
    let s = cache.get(key);
    if (!s) {
      s = pointStyle(state, color, ctx.tokens, ctx.motion);
      cache.set(key, s);
    }
    perPoint.set(p, s);
    return s;
  };
  return {
    getFillColor: (p: StyledPoint) => style(p).fill,
    getRadius: (p: StyledPoint) => style(p).radius,
    getLineColor: (p: StyledPoint) => style(p).line,
    getLineWidth: (p: StyledPoint) => style(p).lineWidth,
  };
}
