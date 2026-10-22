# Judging guidelines

Relevance judgments are the ground truth of the evaluation (base.md §12.3). They must come from
**listening**, never from system output (CLAP scores, ranks, titles alone).

## How

```bash
# fastest: play each clip once and rate it against every query
uv run python scripts/judge.py --judge "<your name>" --play "cvlc --play-and-exit --quiet {path}" --by-track

# one query at a time, or one track at a time
uv run python scripts/judge.py --judge "<your name>" --play "cvlc --play-and-exit --quiet {path}" --query q01
uv run python scripts/judge.py --judge "<your name>" --play "cvlc --play-and-exit --quiet {path}" --track 76075
```

`{path}` is filled in by the script; any player works (`mpv --really-quiet {path}`,
`ffplay -nodisp -autoexit {path}`), or leave out `--play` and open the printed path yourself.

The clip plays in the background: answer as soon as you have heard enough, there is no need
to wait for it to end. In `--by-track` mode the clip keeps playing across that track's queries
and stops when the next track starts; otherwise it stops as soon as a pair is answered.

At any prompt: `r` replays the clip, `x` stops it, `s` skips the pair, `q` (or Ctrl+C) stops
judging. Invalid answers are asked again. Every answered pair is saved immediately, so you can
stop and resume at any time; judged pairs never come back.

Judge the full grid of 20 queries x 20 tracks (400 pairs). Most pairs are an instant `0`:
answer those as soon as you can tell. Judge the query as written; do not reinterpret it.

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
