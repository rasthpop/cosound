// Genre scale tests.
//
// Palette validation (dataviz skill, scripts/validate_palette.js, OKLab ΔE ×100, run 2026-11-02):
//
//   dark  #3987E5,#D95926,#199E70,#C98500,#D55181,#008300,#9085E9,#E66767  on #0B0B0F
//     adjacent:  PASS L band 0.48-0.67 · PASS chroma ≥ 0.10 · PASS CVD worst 8.4 (aqua↔yellow,
//                protan) · PASS normal-vision worst 19.3 · PASS contrast, all 8 ≥ 3:1
//     all pairs: FAIL CVD worst 1.6 (magenta↔aqua, deutan) · FAIL normal-vision 7.1 (red↔orange)
//   light #2A78D6,#EB6834,#1BAF7A,#EDA100,#E87BA4,#008300,#6250D6,#E34948  on #F4F4F7
//     adjacent:  PASS L band · PASS chroma · PASS CVD worst 9.1 · PASS normal-vision worst 19.6 ·
//                WARN contrast: orange 2.92, aqua 2.56, yellow 1.97, magenta 2.45 (< 3:1)
//     all pairs: FAIL CVD worst 3.2 (green↔orange, protan) · FAIL normal-vision 7.1 (red↔orange)
//
// A scatter map is an all-pairs form, and the skill caps such forms at three hues. ui.md §2 asks
// for 8-10 genre hues (fma_small has 8 top-level genres), so the map keeps eight and does not
// rely on hue alone:
//   - genre is always named in text: the legend (from `MapMeta.genres`) and the point tooltip;
//   - the legend isolates one genre at a time (U03.T04), which is the skill's "facet" remedy;
//   - UMAP places similar audio together, so genres also read as regions, not only as hues;
//   - the results list is the keyboard and screen-reader path to the same tracks.
// The light-theme contrast WARN takes the same text relief. Selection and results never use
// colour at all (pointStates: size + ring).
import { describe, expect, it } from "vitest";

import { dark, light } from "../tokens/semantic";
import { genreScale, type GenreCountLike } from "./categorical";

const FMA: GenreCountLike[] = [
  { genre: "Instrumental", count: 1000 },
  { genre: "International", count: 1000 },
  { genre: "Pop", count: 1000 },
  { genre: "Electronic", count: 999 },
  { genre: "Experimental", count: 999 },
  { genre: "Folk", count: 999 },
  { genre: "Hip-Hop", count: 998 },
  { genre: "Rock", count: 998 },
];

describe("genreScale", () => {
  it("assigns palette slots by genre name, independent of input order and counts", () => {
    const a = genreScale(FMA, dark);
    const shuffled = [...FMA].reverse().map((g, i) => ({ ...g, count: 500 + i }));
    const b = genreScale(shuffled, dark);
    for (const { genre } of FMA) expect(b.colorOf(genre)).toBe(a.colorOf(genre));
    // alphabetical: Electronic is slot 1, Rock slot 8
    expect(a.colorOf("Electronic")).toBe(dark.color.map.categorical[0]);
    expect(a.colorOf("Rock")).toBe(dark.color.map.categorical[7]);
    expect(new Set(FMA.map((g) => a.colorOf(g.genre))).size).toBe(8);
  });

  it("is case-insensitive and stable when called again", () => {
    const s = genreScale(FMA, dark);
    expect(s.colorOf("hip-hop")).toBe(s.colorOf("Hip-Hop"));
    expect(genreScale(FMA, dark).colorOf("Folk")).toBe(s.colorOf("Folk"));
  });

  it("maps a null genre to the neutral token, never to a category", () => {
    const s = genreScale([...FMA, { genre: null, count: 7 }], dark);
    expect(s.colorOf(null)).toBe(dark.color.map.point.default);
    expect(dark.color.map.categorical).not.toContain(s.colorOf(null));
    expect(s.legend.at(-1)).toEqual({ genre: null, kind: "none", color: dark.color.map.point.default, count: 7 });
  });

  it("folds genres beyond the palette into Other, keeping the largest genres coloured", () => {
    const many = [...FMA, { genre: "Blues", count: 3 }, { genre: "Classical", count: 2 }];
    const s = genreScale(many, dark);
    expect(s.colorOf("Blues")).toBe(dark.color.map.point.other);
    expect(s.colorOf("Classical")).toBe(dark.color.map.point.other);
    expect(s.colorOf("Unknown genre")).toBe(dark.color.map.point.other);
    expect(s.legend.find((e) => e.kind === "other")?.count).toBe(5);
    expect(s.legend.filter((e) => e.kind === "genre")).toHaveLength(8);
    // adding small genres does not repaint the coloured ones
    for (const { genre } of FMA) expect(s.colorOf(genre)).toBe(genreScale(FMA, dark).colorOf(genre));
  });

  it("follows the theme", () => {
    expect(genreScale(FMA, light).colorOf("Electronic")).toBe(light.color.map.categorical[0]);
    expect(genreScale(FMA, light).colorOf(null)).toBe(light.color.map.point.default);
  });

  it("builds the legend in API order with counts, and handles an empty summary", () => {
    const s = genreScale(FMA, dark);
    expect(s.legend.map((e) => e.genre)).toEqual(FMA.map((g) => g.genre));
    expect(s.legend.reduce((n, e) => n + e.count, 0)).toBe(FMA.reduce((n, g) => n + g.count, 0));
    const empty = genreScale([], dark);
    expect(empty.legend).toEqual([]);
    expect(empty.colorOf("Rock")).toBe(dark.color.map.point.other);
  });
});
