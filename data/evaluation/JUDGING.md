# Judging guidelines

Relevance judgments are the ground truth of the evaluation (base.md §12.3). They must come from
**listening**, never from system output (CLAP scores, ranks, titles alone).

## How

```bash
uv run python scripts/judge.py --judge "<your name>" --play "mpv --really-quiet {path}"
```

Any player works (`ffplay -nodisp -autoexit {path}`, `vlc --play-and-exit {path}`), or leave out
`--play` and open the printed path yourself. Pairs come in a fixed shuffled order; answers are
saved after every pair, so you can stop with `q` and resume later. `s` skips a pair.

Judge the full grid of 20 queries × 20 tracks (400 pairs). It avoids pooling bias, and the
clips are 30 s each. Judge the query as written; do not reinterpret it.

## Scale

| Field | Values | When asked |
|---|---|---|
| `overall_relevance` | **3** strong match · **2** good match · **1** partial match · **0** not relevant | always |
| `mood_relevance` | 0-3, the same scale for the mood alone | query names a mood |
| `instrument_present` | `yes` / `no` / `uncertain` | query names an instrument |
| `constraint_satisfied` | `yes` / `no` / `unknown` | query has a hard constraint (e.g. "without vocals") |
| `basis` | short note of what you heard | always |

- A track is counted as **relevant** when `overall_relevance >= 2`.
- `instrument_present`: answer `yes` only if you clearly hear it. A title or tag mentioning the
  instrument is not evidence. Use `uncertain` whenever you are not sure.
- `constraint_satisfied`: `unknown` if you cannot tell (e.g. a vocal sample you cannot classify).
- `basis` example: "soft flute lead over pads, slow", "rap vocals throughout".

Judging requires the 20 manifest tracks to be the final ones: finish the listening pass in
`README.md` (confirm or replace tracks) before judging, or judgments for replaced tracks will
have to be redone.
