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

The target is the full grid of 20 queries x 20 tracks (400 pairs). Most pairs are an instant
`0`: answer those as soon as you can tell. Judge the query as written; do not reinterpret it.
Judge a query against all 20 tracks or not at all: a partly judged query is refused by
calibration.

## Documented minimum (2026-10-22, owner)

Fewer than 400 pairs are judged before calibration. The minimum is recorded in
`judging_minimum.json`, and `scripts/calibrate.py` checks it.

| Split | Queries | Pairs | State on 2026-10-22 |
|---|---|---|---|
| dev, required for calibration | q01 q03 q06 q10 q11 q12 q16 q18 | 160 | all judged (160/160) |
| dev, deferred | q07 q08 | 40 | unjudged, left out of calibration |
| test, required | q02 q04 q05 | 60 | all judged (60/60) |
| test, deferred | q09 q13 q14 q15 q17 q19 q20 | 140 | unjudged, left out of test metrics |

- Calibration uses the 8 required dev queries (plus q07/q08 only if they get fully judged later).
  Its nDCG@5 is therefore a mean over at most 8 queries, and q07/q08 (gradual build, rhythmic
  playfulness) are the structure-heavy requests the grid never sees.
- Test metrics (P10) are means over the 3 judged test queries. The report names the 7 unjudged
  ones as left out; with n=3, test numbers show the workflow, not a quality claim.
- A query is judged against all 20 tracks or not at all; a partly judged query is flagged in
  the report as incomplete.

```bash
uv run python scripts/judge.py --judge "<your name>" --play "cvlc --play-and-exit --quiet {path}" --by-track \
  --query q10 --query q11 --query q12 --query q16 --query q18
```

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
