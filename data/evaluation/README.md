# Evaluation data

Fixed inputs for the small, reproducible evaluation (base.md §12). Everything here is tracked
in git; audio files are not.

## `fma_20_manifest.csv` — the 20-track corpus (draft, pending listening)

**Status:** drafted from metadata on 2026-10-20 by `scripts/make_fma_manifest.py` (seed 42,
FMA metadata archive SHA-1 `f0df49ffe5f2a6008d7dc83c6915b31835dfe733`). **Not frozen yet:**
every row has `listening_status=pending` until someone has listened to it.

### How the draft was chosen

1. Pool: the 8,000 `fma_small` tracks that have a title, an artist, and a license that
   permits research use (Creative Commons / CC0 / public domain; 5 tracks without a license
   are excluded).
2. One pass per query theme from base.md §12.2, using metadata only: genres, title/tags,
   and echonest estimates where available (only 1,294 of the 8,000 tracks have them).
   Themes and counts are in the `theme` and `selection_reason` columns.
3. Two deliberate challenging negatives that share genres with positive picks but should
   not match their queries (energetic Folk; speech-heavy Hip-Hop).
4. At most one track per artist; ties go to top genres not yet covered; remaining ties are
   broken by a seeded hash, so the same inputs always give the same file.

Coverage of the 8 `fma_small` top genres: Electronic 5, Folk 4, International 3, Pop 3,
Rock 3, Experimental 1, Hip-Hop 1, **Instrumental 0** (consider swapping one track in during
the listening pass).

Metadata cannot show how a track sounds. A title containing "flute" does not prove a flute
is audible, and a genre tag does not prove a mood. That is why listening is required.

### What the owner needs to do

1. **Audio is already in place** once `fma_small` is downloaded (`scripts/download_fma.py --subset small`,
   ADR-0005): every listed file lives at `DATA_DIR/<audio_path>`, e.g.
   `data/raw/fma/fma_small/076/076075.mp3`. All 20 decoded on 2026-10-21.
2. **Check decoding:** `uv run python scripts/make_fma_manifest.py --check-audio`.
3. **Listen to every track.** For each row set `listening_status` to `confirmed`, or replace
   the row with a better track for that theme (keep the theme, update `selection_reason`
   with what you heard and why). Record replacements in the change log below.
4. **Freeze.** When every row is `confirmed`, note the date below. From then on the file is
   never regenerated; `make_fma_manifest.py` refuses to overwrite a changed file without
   `--force`, and the evaluation will verify checksums (P10.T01).

### Change log

| Date | Change | By |
|---|---|---|
| 2026-10-20 | Initial metadata draft (20 rows, all pending) | P02.T10 |

### Columns

| Column | Meaning |
|---|---|
| `fma_track_id` | FMA track id (also the audio file name) |
| `title`, `artist`, `genre` | From FMA `tracks.csv`; `genre` is `genre_top` |
| `audio_path` | Relative to `DATA_DIR` |
| `source` | `fma_small` |
| `license` | Per-track license from FMA metadata |
| `split` | Always `corpus`: dev/test splits are by **query**, defined in `split.json` (P05) |
| `theme` | Query theme the track was drafted for |
| `selection_reason` | Why it was picked (metadata evidence, later: what was heard) |
| `listening_status` | `pending` → `confirmed` after listening |
