# ADR-0005: FMA-only MVP; Discogs deferred

- **Status:** Accepted (project owner, 2026-10-21)
- **Date:** 2026-10-21
- **Phase/Task:** P02 (scope change), affects P04, P07, P08, P09, P10

## Context

`base.md` lists Discogs as a core requirement (§1 req. 2, §2, §10): the catalog source for metadata, artist/label/release relationships, and `discogs_url` links, with FMA as the audio corpus joined to Discogs only through reliable matches.

Building P02 showed three things:

- The Discogs Terms of Use cannot be read by automated tools (HTTP 403), so the storage and attribution rules for a cached catalog are still unconfirmed.
- Searching Discogs by style requires a token, and the bounded import can't run without one.
- Reliable FMA↔Discogs matches will be rare. FMA artists are mostly independent and seldom listed on Discogs, and the matcher (rightly) refuses weak matches. So Discogs would add few facts to the tracks that actually have audio.

The MVP goal is the end-to-end loop: *a user describes a song → FMA metadata + CLAP audio + the agents find, rank and explain matches → feedback refines them.* Every part of that loop works with FMA alone.

## Decision

For the MVP, **FMA is the only catalog and audio source.**

- The catalog is the full **`fma_small`** subset: 8,000 tracks with 30-second clips in 8 balanced top genres, downloaded and checksum-verified (`scripts/download_fma.py --subset small`), git-ignored under `data/raw/fma/`.
- Metadata retrieval uses FMA fields: titles, artist and album names, the genre hierarchy (`genres_all`), tags, and echonest estimates (weak evidence, about 1,300 tracks).
- Relationships come from FMA only: same artist, same album.
- Links: a new generic `Track.source_url` (the FMA track page, from `raw_tracks.csv`). The API exposes `source_url` instead of `discogs_url`. Because FMA audio is Creative Commons and stored locally, the API may serve a short preview of it (P08).
- The 20-track evaluation corpus is unchanged: a fixed subset of `fma_small` (P02.T10).

**Discogs is deferred, not removed.** The client, normalizer, bounded importer, raw cache, selection config and cross-source matcher from P02 stay in the repository with their tests. They are marked post-MVP in the phase plan (status `[-]`) and are not on the MVP path. `Track.discogs_url` stays in the schema, always null for now.

## Consequences

- **Deviation from base.md:** requirement 2 ("Discogs-based music metadata and artist, label, and release relationships") is not met by the MVP. Label relationships and master/release versioning are unavailable. Genres come from FMA's taxonomy instead of Discogs styles.
- The metadata signal is thinner than Discogs styles would give (FMA has few tags: only 1,361 of the 8,000 tracks have any). Hybrid ranking will lean more on CLAP; the evaluation reports this.
- Every MVP track has a licensed local audio file, so semantic scores exist for every track that decodes. The "metadata-only track" path stays implemented and tested, but is rare in the MVP catalog.
- About 7.2 GiB of audio plus derived embeddings live locally. Nothing is committed.
- API and UI contracts use `source_url`; no Discogs attribution is needed in the MVP UI. FMA metadata attribution (CC BY 4.0) is required.

## Reversible by

Run P02.T11 (live bounded Discogs import) and P02.T08's matcher, then turn the deferred P04/P08 items back on. The domain model already has `discogs_url`, the Discogs `ExternalId`s, the relationship types and the match records, so re-enabling Discogs adds data without changing the schema or the API shape (`discogs_url` would return beside `source_url`).
