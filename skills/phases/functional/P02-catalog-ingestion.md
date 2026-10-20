# P02 — Catalog Ingestion: Discogs, FMA, Relationships, Matching

**Goal:** a local, normalized, provenance-preserving catalog built from a bounded Discogs import and the FMA metadata/audio, queryable with no live Discogs request (Milestone 1).
**base.md:** §2 (metadata vs audio), §10, §12.1, §16.
**Depends on:** P01

### P02.T01 — Data-source terms & licensing review
- **Skills:** discogs-ingestion, fma-audio-corpus
- **Depends on:** P00
- **Files:** docs/data-sources.md
- **Do:**
  - Read Discogs API terms, attribution, caching/storage and rate-limit rules; FMA dataset and per-track license terms. Record what is allowed (caching duration, display attribution, fixture storage), with the date read and links.
  - List any constraint that changes the plan (e.g. caching limits) as a blocker for the user.
- **Done when:**
  - `docs/data-sources.md` exists with sections Discogs / FMA / Implications; user has acknowledged any blockers.
- **Notes:** The Discogs Terms of Use page returns 403 to automated access; rate limits, headers, auth, pagination and the CC0/Restricted split were recorded from the API docs text. Reading the full terms is listed as an open item for the owner in `docs/data-sources.md`; fixtures are synthetic so no Discogs content is committed.
- **Status:** [x]

### P02.T02 — Discogs client
- **Skills:** discogs-ingestion
- **Depends on:** P01.T05, P02.T01
- **Files:** src/music_discovery/ingestion/discogs_client.py, src/music_discovery/ingestion/discogs_models.py, src/music_discovery/ingestion/rate_limit.py, tests/integration/ingestion/test_discogs_client.py
- **Do:**
  - Auth + User-Agent headers, token-bucket limiter adapted from rate-limit headers, retries with jittered backoff, pagination bounded by `max_items`, error classification, structured request logs with token redaction. Injected clock/sleep.
- **Done when:**
  - MockTransport tests cover: success, 404, 401, 429 with/without Retry-After, 5xx→success, timeout, malformed JSON, pagination stopping at `max_items`, header-driven slowdown.
  - No test performs network I/O (socket blocked in conftest).
- **Notes:** One unauthenticated `GET /releases/249504` was made by hand while reading the docs, to confirm the rate-limit headers; nothing from it was stored. Tests never touch the network: `tests/conftest.py` blocks sockets unless a test is marked `live`.
- **Status:** [x]

### P02.T03 — Discogs normalizer & fixtures
- **Skills:** discogs-ingestion, domain-modeling
- **Depends on:** P02.T02, P01.T02
- **Files:** src/music_discovery/ingestion/normalizer.py, tests/fixtures/discogs/*.json, tests/unit/ingestion/test_normalizer.py
- **Do:**
  - Raw release/master/artist/label → domain entities; tracklist handling (headings, index sub-tracks, durations), artist disambiguators/ANVs/joins, master links, genres/styles with `source="discogs"`, `discogs_url` from API `uri`.
- **Done when:**
  - Fixture-driven tests for each normalization rule; one release produces the expected number of `Track`s with structured artists.
- **Status:** [x]

### P02.T04 — Bounded, reproducible Discogs importer
- **Skills:** discogs-ingestion
- **Depends on:** P02.T03, P01.T07
- **Files:** src/music_discovery/ingestion/catalog_importer.py, config/discogs_selection.yaml, scripts/import_discogs.py, tests/integration/ingestion/test_catalog_importer.py
- **Do:**
  - Selection config with `selection_version`, seeds and caps; raw response cache under `data/raw/discogs/`; normalization from cache; `import_runs` record (selection hash, counts, errors, timestamps); per-release transactions; `--from-cache-only` and `--dry-run` flags.
  - Document the bounded import procedure in `docs/data-sources.md#import`.
- **Done when:**
  - Running twice with the same selection yields identical catalog row counts and IDs.
  - A simulated mid-run failure leaves previously imported releases intact and the failed one absent.
  - `--from-cache-only` works with the network disabled.
- **Notes:** Added an `ImportRun` model, `ImportRunRepository` (fake + SQL) and an `imp_` id prefix. Seed listings are cached alongside releases, so `--from-cache-only` works for every seed type. Artist aliases and label external ids are merged across releases instead of overwritten.
- **Status:** [x]

### P02.T05 — FMA acquisition
- **Skills:** fma-audio-corpus
- **Depends on:** P02.T01
- **Files:** scripts/download_fma.py (or docs/fma-setup.md), docs/data-sources.md
- **Do:**
  - Download `fma_metadata.zip` and `fma_small.zip` to `${DATA_DIR}/raw/fma/`, verify checksums, unpack; idempotent; never under git.
- **Done when:**
  - Script/doc reproduces the layout; checksums verified and recorded.
- **Notes:** Owner decision: only `fma_metadata.zip` is downloaded (checksum verified, unpacked); `fma_small` is not. The owner places the 20 evaluation audio files manually.
- **Status:** [x]

### P02.T06 — FMA loader, audio probe & import
- **Skills:** fma-audio-corpus, domain-modeling
- **Depends on:** P02.T05, P01.T07
- **Files:** src/music_discovery/ingestion/fma_loader.py, src/music_discovery/audio/audio_probe.py, scripts/import_fma.py, tests/fixtures/fma/, tests/integration/ingestion/test_fma_loader.py
- **Do:**
  - Load `tracks.csv` (two-row header), `genres.csv`, optional `echonest.csv` (weak, estimated features); resolve audio paths; validate decodability through the `AudioProbe` protocol (concrete probe in `audio/`); import `Track` + `TrackAudio` with `source="fma"`, license, FMA genres; import report of failures.
- **Done when:**
  - Fixture tests: header parsing, list columns, path resolution, decode success/failure via a generated sine wav and an empty file, license captured, `audio_available` derived from validation.
- **Notes:** Decodable audio is represented by a `TrackAudio` record and `Track.audio_path`; `Track.audio_available` stays tied to embeddings (analysis), so a decodable but unanalyzed track is still `metadata_only`. Echonest features are loaded (weak, estimated) but not stored yet. Probe uses `soundfile` (libsndfile with MP3 support) in `audio/`.
- **Status:** [x]

### P02.T07 — Relationship graph
- **Skills:** discogs-ingestion
- **Depends on:** P02.T04, P02.T06
- **Files:** src/music_discovery/ingestion/relationships.py, tests/unit/ingestion/test_relationships.py
- **Do:**
  - Derive `same_artist`, `same_label`, `same_master`, `same_release`, `shared_style` (rarity-weighted) edges with `evidence_source`; persist; recompute idempotently.
- **Done when:**
  - Tests on a fixture catalog give the expected edges; no edge without evidence source.
- **Notes:** Added `RelationshipRepository.replace_all` for idempotent recomputation. Shared-style edges are IDF-weighted, capped at top-k per track; groups above `max_group_size` are skipped.
- **Status:** [x]

### P02.T08 — Conservative FMA ↔ Discogs matcher
- **Skills:** discogs-ingestion, fma-audio-corpus
- **Depends on:** P02.T04, P02.T06
- **Files:** src/music_discovery/ingestion/matcher.py, scripts/match_sources.py, tests/unit/ingestion/test_matcher.py
- **Do:**
  - Normalization, blocking, signal scoring, acceptance rule (title AND artist AND corroboration AND unique), `unresolved` storage with candidates, provenance/confidence on every match; match report (accepted/unresolved/none counts).
- **Done when:**
  - Tests: exact match accepted; title-only and artist-only rejected; two equal candidates ⇒ unresolved; duration contradiction ⇒ rejected; FMA IDs never compared to Discogs IDs.
- **Notes:** Three outcomes are stored: `accepted`, `unresolved` (ambiguous or uncorroborated) and `rejected` (title+artist agree but duration contradicts).
- **Status:** [x]

### P02.T09 — Offline catalog query check (M1 acceptance)
- **Skills:** music-discovery-architecture
- **Depends on:** P02.T04, P02.T06, P02.T08
- **Files:** scripts/catalog_stats.py, tests/integration/test_catalog_offline.py
- **Do:**
  - CLI printing counts (tracks, with audio, with Discogs match, by source/genre), and a lookup by title/artist — using only the local DB.
- **Done when:**
  - Integration test with network disabled imports from fixtures/cache and queries tracks successfully.
- **Status:** [x]

### P02.T10 — Fixed 20-track evaluation manifest
- **Skills:** fma-audio-corpus, retrieval-evaluation
- **Depends on:** P02.T06
- **Files:** scripts/make_fma_manifest.py, data/evaluation/fma_20_manifest.csv, data/evaluation/README.md
- **Owner:** human-in-the-loop (listening required for the contrast picks)
- **Do:**
  - Implement the deterministic selection procedure (genre stratification + listened contrast picks + challenging negatives), license filter, `selection_reason` column; refuse overwrite without `--force`.
  - Use the draft query themes from base §12.2 as guidance for which sonic contrasts to include.
- **Done when:**
  - 20 rows, all audio valid, licenses recorded, README documents seed/date/procedure; re-run reproduces the file byte-for-byte.
- **Notes:** Drafted from metadata on 2026-10-20 (owner decision): 20 tracks, 20 artists, 7 of 8 top genres (no Instrumental), every row `listening_status=pending`. Blocked until the owner places the audio, runs `--check-audio`, listens, and confirms or replaces rows (see `data/evaluation/README.md`).
- **Status:** [!]

### P02.T11 — Live bounded Discogs import
- **Skills:** discogs-ingestion
- **Depends on:** P02.T04, P02.T01
- **Files:** .env (local only), config/discogs_selection.yaml
- **Owner:** human (needs a Discogs token and a read of the Terms of Use)
- **Do:**
  - Read the Discogs API Terms of Use in a browser and update `docs/data-sources.md` (Restricted Data, caching, attribution).
  - Put `DISCOGS_TOKEN` and `DISCOGS_USER_AGENT` in `.env`; review the seeds and caps in `config/discogs_selection.yaml`.
  - Run `uv run python scripts/import_discogs.py`, then `scripts/build_relationships.py` and `scripts/match_sources.py`; record the counts here.
- **Done when:**
  - A bounded import run is recorded in `import_runs` with no unexpected errors, and `scripts/catalog_stats.py` shows Discogs tracks.
- **Status:** [ ]

## Exit criteria (Milestone 1)
- [x] A local catalog can be queried without a live Discogs request (P02.T09 test green).
- [x] Track IDs stable across re-imports; cross-source matches carry provenance and confidence.
- [x] Every track has explicit audio availability.
- [ ] `fma_20_manifest.csv` committed and frozen. *(Committed as a draft; frozen after the owner's listening pass, P02.T10.)*
