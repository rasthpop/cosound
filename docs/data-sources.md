# Data sources: terms, licensing and implications

> **MVP scope:** FMA only ([ADR-0005](adr/0005-fma-only-mvp.md)). The Discogs section stays for the deferred post-MVP import.

Read on 2026-10-20 (P02.T01). Re-check before any large import or before publishing data.

## Discogs

**What was verified**

| Topic | Finding | Source |
|---|---|---|
| Rate limits | 60 requests/min authenticated, 25/min unauthenticated, moving 60-second window per source IP; resets after 60 s without requests | Discogs API docs (via a mirror of the official text; see below) |
| Rate-limit headers | `X-Discogs-Ratelimit`, `X-Discogs-Ratelimit-Used`, `X-Discogs-Ratelimit-Remaining` | API docs; confirmed on one unauthenticated `GET /releases/249504` (headers showed `25 / 0 used / 25 remaining`) |
| User-Agent | Required; must identify the application (RFC 1945 style). Without it responses may come back empty | API docs |
| Authentication | Key/secret (public data, higher rate limit), personal access token, or OAuth 1.0a. Header form for tokens: `Authorization: Discogs token=<token>` | API docs |
| Pagination | `page` and `per_page`; default 50, maximum 100 | API docs |
| Data licensing | "Some Discogs data is made available under the CC0 No Rights Reserved license, and some is restricted data, as defined in our API Terms of Use." | API docs |
| Terms version | API Terms of Use page last updated 2025-05-27 | search result snippet |

**What could not be verified**

The Terms of Use page (https://support.discogs.com/hc/en-us/articles/360009334593) and the developer docs (https://www.discogs.com/developers) return HTTP 403 to automated requests, so the exact definition of **Restricted Data**, caching duration limits, and attribution wording were not read. **Open item for the project owner:** read the Terms of Use in a browser and update this section.

**Implications for this project (until the terms are read in full)**

- Import only release-level catalog metadata: titles, artists, labels, genres, styles, years, track listings, master links, and the `uri` link. Do not store images, marketplace data, prices, user data, ratings or collections.
- Keep the import bounded (`config/discogs_selection.yaml`, `max_releases`) and never parallelize requests to beat the rate limit.
- Raw responses are cached locally under `data/raw/discogs/` (git-ignored) and are never committed or redistributed.
- Test fixtures under `tests/fixtures/discogs/` are **hand-written synthetic payloads** with the API's shape, not recorded responses, so no Discogs content is committed.
- Show a Discogs attribution and link (`discogs_url` from the API `uri`) wherever Discogs metadata is displayed. Final wording follows the terms once read.
- Discogs also publishes monthly data dumps; their license (believed CC0) should be confirmed before they are considered as an alternative to the API.

<a id="import"></a>
### Bounded import procedure

1. Edit `config/discogs_selection.yaml`: bump `selection_version` when the selection changes; keep `max_releases` small.
2. Put `DISCOGS_TOKEN` (optional, raises the limit to 60/min) and `DISCOGS_USER_AGENT` in `.env`.
3. Fetch into the raw cache and normalize: `uv run python scripts/import_discogs.py`.
4. Re-normalize from the cache without network access: `uv run python scripts/import_discogs.py --from-cache-only`.
5. Preview what would be fetched: `uv run python scripts/import_discogs.py --dry-run`.

Each run is recorded in the `import_runs` table with the selection hash, counts and errors. Re-running the same selection produces the same internal ids and row counts.

## FMA (Free Music Archive dataset)

Source: https://github.com/mdeff/fma

| Archive | URL | Size | SHA-1 |
|---|---|---|---|
| `fma_metadata.zip` | https://os.unil.cloud.switch.ch/fma/fma_metadata.zip | 342 MiB | `f0df49ffe5f2a6008d7dc83c6915b31835dfe733` |
| `fma_small.zip` | https://os.unil.cloud.switch.ch/fma/fma_small.zip | 7.2 GiB | `ade154f733639d52e35e32f5593efe5be76c6d70` |

**Licensing** (quoted from the FMA README):

- Code: "released under the MIT license."
- Metadata: "released under the Creative Commons Attribution 4.0 International License (CC BY 4.0)."
- Audio: "We do not hold the copyright on the audio and distribute it under the license chosen by the artist." Each track's license is the `('track', 'license')` column of `tracks.csv`.
- "The dataset is meant for research purposes."

**Implications**

- Metadata may be used with attribution (CC BY 4.0): credit the FMA dataset (Defferrard et al.) in the README and evaluation report.
- Audio stays local under `data/raw/fma/` and is never committed. Each track's license is stored with its `TrackAudio` record and in the evaluation manifest.
- The evaluation manifest only selects tracks whose license permits research use (P02.T10).
- MVP (ADR-0005): both `fma_metadata.zip` and `fma_small.zip` are downloaded by `scripts/download_fma.py` into the git-ignored `data/raw/fma/`. The full `fma_small` subset is the MVP catalog; the 20 evaluation tracks are a fixed subset of it (`data/evaluation/README.md`).

## Status

- [x] Discogs rate limits, headers, auth, pagination, data-licensing split recorded.
- [ ] **Discogs Terms of Use read in full** (Restricted Data definition, caching limits, attribution). Blocked for automated access; owner to review.
- [x] FMA archive URLs, checksums and licenses recorded.
