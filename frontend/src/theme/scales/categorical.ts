// Genre colours for the map (ui.md §2 "Point color"). Pure functions of the API's genre summary
// (`MapMeta.genres`) and the active theme's tokens; no genre list is hard-coded here.
//
// - Domain: the most frequent genres in `MapMeta.genres`, up to the palette size. That summary
//   covers the whole projection and ignores filters and pagination, so the domain, and every
//   colour in it, stays fixed while the user filters or pages.
// - Assignment: domain genres sorted by name, then given slots in order. A genre's colour
//   depends on its name and the domain, never on load order or on its rank by count.
// - `null` genre → the neutral `map.point.default` token, never a category. A genre outside the
//   domain → `map.point.other` ("Other").
import type { Color, SemanticTokens } from "../tokens/types";

/** The input this scale needs; structurally `MapMeta["genres"][number]` from the API. */
export interface GenreCountLike {
  genre: string | null;
  count: number;
}

export type GenreKey = string | null;

export interface LegendEntry {
  /** The genre name as the API sent it; `null` for points without a genre; `"other"` kind for the fold. */
  genre: string | null;
  kind: "genre" | "other" | "none";
  color: Color;
  count: number;
}

export interface GenreScale {
  colorOf(genre: GenreKey): Color;
  /** Legend rows in `MapMeta.genres` order (count desc), with the folded "Other" row and the no-genre row. */
  legend: LegendEntry[];
}

const key = (genre: string) => genre.trim().toLocaleLowerCase("en");
const byName = (a: string, b: string) => key(a).localeCompare(key(b), "en") || a.localeCompare(b, "en");

export function genreScale(genres: readonly GenreCountLike[], tokens: SemanticTokens): GenreScale {
  const palette = tokens.color.map.categorical;
  const named = genres.filter((g): g is GenreCountLike & { genre: string } => g.genre !== null);
  // the largest genres get hues; ties by name so the cut is deterministic
  const domain = [...named]
    .sort((a, b) => b.count - a.count || byName(a.genre, b.genre))
    .slice(0, palette.length)
    .map((g) => g.genre)
    .sort(byName);
  const slots = new Map<string, Color>();
  domain.forEach((genre, i) => {
    const color = palette[i];
    if (color !== undefined && !slots.has(key(genre))) slots.set(key(genre), color);
  });

  const none = tokens.color.map.point.default;
  const other = tokens.color.map.point.other;
  const colorOf = (genre: GenreKey): Color => (genre === null ? none : (slots.get(key(genre)) ?? other));

  const legend: LegendEntry[] = [];
  let otherCount = 0;
  for (const g of genres) {
    if (g.genre === null) continue;
    if (slots.has(key(g.genre))) legend.push({ genre: g.genre, kind: "genre", color: colorOf(g.genre), count: g.count });
    else otherCount += g.count;
  }
  if (otherCount > 0) legend.push({ genre: null, kind: "other", color: other, count: otherCount });
  const noGenre = genres.filter((g) => g.genre === null).reduce((sum, g) => sum + g.count, 0);
  if (noGenre > 0) legend.push({ genre: null, kind: "none", color: none, count: noGenre });

  return { colorOf, legend };
}
