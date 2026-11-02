# Visual reference check (U01.T01)

The UI/UX plan (`skills/phases/ui/ui.md`) names Subwave, *"See the shape of your library"*
(https://www.getsubwave.com/news/see-the-shape-of-your-library), as its visual reference. U01.T01
checks it and adjusts **token values only, never structure**. Checked 2026-11-02.

## What the reference contains

The page is an editorial article. It has no stylesheet values, colours, font names or
screenshots that could be read. What it describes:

- A full-screen "Library Observatory" map: every tagged track is a point, placed near tracks of
  its genre.
- Points lit on an **"ink-to-vermilion ramp"** by energy, with faint lines to close neighbours.
- Stat panels down the right side, filters on a left rail, pan and scroll-to-zoom, and a click
  that opens the track's record and nearest tracks.
- A print-like editorial voice ("№ 01", "VOL. 1.29.0"), which is an impression from the text,
  not a stated design.

## What the tokens match, and what they don't

| Reference | Tokens | Decision |
|---|---|---|
| Dark full-screen map, points as a field | `surface.canvas`/`map.backdrop` `#0B0B0F`, point opacity 0.55, dimmed 0.15 | Matched; values come from ui.md §2. |
| Ink-to-vermilion ramp | `match.weak/partial/strong`: ink grey → vermilion | **Adopted for match-strength bands.** The plan has no energy field (energy colouring would need a contract request), but match strength is a sequential magnitude, so the reference's ramp encodes it. This is a value change only. |
| Colour by energy, position by genre | Points coloured by genre (`theme/scales/categorical`, U01.T03) | Not matched. ui.md §2 colours points by `MapPoint.genre`, and the API exposes no energy. |
| Faint lines to neighbours | none | Not matched. It isn't in ui.md, so it would be a new map layer (structure), not a value. |
| Panels on the right, controls on the left | Glass panels: `surface.panel` `rgba(18,18,24,0.72)`, blur 12, hairline border, radius 16 | The layout belongs to ui.md §3. Panel values come from the plan. |
| Editorial type | Inter 13/15/20/28, weights 400/500 | Kept the plan's single sans family. |
| Vermilion as a highlight | Accent stays violet `#A78BFA` | Kept the plan's default accent for focus, selection and the primary action. Vermilion appears only in the match ramp, so there is still exactly one accent. |

## Contrast

`frontend/src/theme/tokens/tokens.test.ts` checks every theme. Translucent panels are composited
over the canvas and over every opaque map pixel the panel can sit on: the backdrop and each point
fill at full opacity, standing in for a dense cluster. That set covers the darkest and the
lightest map pixel. U01.T03 adds the genre fills to this set.

| Theme | Body text (min) | Muted text (min) | Marks: focus / match weak·partial·strong / error / warning (min) |
|---|---|---|---|
| dark | 11.3 | 5.3 | 4.6 / 5.8·7.4·9.6 on canvas (≥ 3.6 everywhere) / 4.5 / 7.4 |
| light | 16.0 | 5.5 | 4.7 / ≈4.1·6.3·9.2 on canvas (≥ 3 everywhere) / 5.3 / 4.1 |

Requirements: text ≥ 4.5:1 and marks ≥ 3:1 on every surface; each match band ≥ 1.2× the contrast
of the band below it, so the ramp reads in order. The light theme's weak band needed a new grey
step (`ink.450`), and its strong band a darker vermilion (`vermilion.800`).

Out of scope here: the WebGL rendering of glowing clusters, which additive blending can make
brighter than one fill. The U05.T01 accessibility audit re-checks panels over real map
screenshots.
