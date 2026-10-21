---
name: fma-audio-corpus
description: Working with the FMA (Free Music Archive) dataset — downloading metadata and audio subsets, loading tracks.csv correctly, resolving audio paths from track IDs, validating decodability, recording per-track licenses, and producing the fixed 20-track evaluation manifest. Load for ingestion/fma_loader.py, scripts/import_fma.py, the evaluation manifest, or any audio-availability question.
---

# FMA Audio Corpus

Spec: `base.md` §2, §9.1, §12.1. Reference: https://github.com/mdeff/fma (README + `utils.py` are the authoritative loader examples).

## 1. Acquisition (task P02.T05)

- Download `fma_metadata.zip` and **`fma_small.zip`** (8,000 × 30 s clips, 8 balanced top genres): `scripts/download_fma.py --subset metadata --subset small`. For the MVP, `fma_small` is the whole catalog (ADR-0005), and the 20-track corpus is a fixed subset of it. Checksums are verified by the script.
- Unpack to `${DATA_DIR}/raw/fma/fma_metadata/` and `${DATA_DIR}/raw/fma/fma_small/`. Never commit audio.
- Record the download date, URLs and checksums in `docs/data-sources.md`. Read the FMA license notes: metadata and code have their own licenses, and **each track has its own Creative Commons license** in `tracks.csv` (`('track', 'license')`). Keep it per track in the manifest.

## 2. Loading metadata

`tracks.csv` has a **two-row header** (MultiIndex columns). Load it like FMA's `utils.load`:

```python
tracks = pd.read_csv(path, index_col=0, header=[0, 1])
# key columns
tracks[("track", "title")], tracks[("artist", "name")], tracks[("album", "title")]
tracks[("track", "genre_top")], tracks[("track", "genres_all")], tracks[("track", "duration")]
tracks[("track", "license")], tracks[("set", "subset")], tracks[("set", "split")]
```

- List-like columns (`genres`, `genres_all`, `tags`) are stringified Python lists → `ast.literal_eval`.
- Filter by `tracks[("set","subset")] <= "small"` (it is an ordered categorical in FMA's loader; replicate or compare explicitly).
- `genres.csv` maps genre ids → titles and parents.
- `echonest.csv` covers only a subset of tracks; where present, features like `instrumentalness`, `acousticness`, `energy`, `tempo` are *estimated* audio features. They may serve as **weak evidence** (with `source="echonest"`, `estimated=True`) — never as ground truth, and absence is `UNKNOWN`.

## 3. Audio paths

```python
def fma_audio_path(audio_dir: Path, track_id: int) -> Path:
    tid = f"{track_id:06d}"
    return audio_dir / tid[:3] / f"{tid}.mp3"
```

The internal ID is derived from the FMA id (`trk_` + uuid5 of `fma:track:{id}`); the FMA id is kept as an `ExternalId`. **FMA track ID ≠ Discogs release ID** — they are never compared.

## 4. Validation (`ingestion/fma_loader.py`)

For each candidate track: file exists → decodes (e.g. `librosa.load(path, sr=None, duration=…)` or `soundfile`/`audioread` for mp3) → duration > ~5 s → not silent (RMS above a tiny floor). A few FMA files are known to be truncated or corrupt — that's why decoding is checked. Record failures in an import report; never silently drop.

(Decoding uses `audio/`'s libraries, so the decode check is implemented as an `AudioProbe` protocol in `domain`, concrete in `audio/`, injected into the loader.)

## 5. The 20-track evaluation manifest (task P05.T01)

`scripts/make_fma_manifest.py` → `data/evaluation/fma_20_manifest.csv` (committed; **generated once, reused forever**).

Selection procedure (deterministic, documented in the CSV header comment or `data/evaluation/README.md`):

1. Pool = `fma_small` tracks that pass validation and whose license permits research use.
2. Stratify across the 8 top genres (≈ 2–3 each) **and** deliberately include acoustic contrasts relevant to the query set: flute/woodwind, piano, female vocals, instrumental, heavy bass, aggressive percussion, ambient/build-ups — chosen by **listening**, and *also* challenging negatives (tracks that share genre tags but not the sound).
3. Fix `random_state` for any sampling step; write `selection_seed`, `fma_version`, `selected_on` and the selector's name to the README.
4. Columns: `fma_track_id,title,artist,genre,audio_path,source,license,split,selection_reason`. `audio_path` is relative to `DATA_DIR`. `split` is unused for tracks (splits are per **query**, see `retrieval-evaluation`) — set to `corpus`.

Re-running the script must reproduce the same file byte-for-byte or refuse to overwrite without `--force`.

## 6. Catalog import (`scripts/import_fma.py`)

- **MVP (ADR-0005):** the catalog is the whole `fma_small` subset: `uv run python scripts/import_fma.py --subset small` (8,000 tracks). Without `--subset` it imports only the manifest tracks.
- Each track becomes `Track` + (when the file decodes) `TrackAudio`, with `source="fma"`: title, artist, album (stored as a `Release`), genres (`genre_top` + direct genres), FMA `tags`, duration, license, `audio_path`, and `source_url` = the FMA track page (`track_url` in `raw_tracks.csv`).
- Decodable audio is a `TrackAudio` record; `Track.audio_available` means analyzed (embedding exists), so it turns true only after P03.
- `preview_url` is not stored: the API serves the local clip at `/api/tracks/{id}/audio` when validated audio exists (P08.T09). Never fabricate links.

## 7. Tests

- Tiny synthetic `tracks.csv` with the real two-row header (3–5 rows) in `tests/fixtures/fma/`.
- Path resolution for ids < 1000 and > 100000.
- A generated 1-s sine wav for decode success, a zero-byte file for failure.
- Manifest determinism: same inputs ⇒ identical CSV.
