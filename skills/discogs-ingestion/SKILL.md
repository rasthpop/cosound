---
name: discogs-ingestion
description: Building and testing the Discogs catalog side — DiscogsClient (auth, User-Agent, rate limiting, pagination, retries, error classification), the bounded reproducible importer, normalization of releases/tracklists/artists/labels, the relationship graph, and conservative FMA↔Discogs matching with provenance. Load for any work in ingestion/discogs_client.py, normalizer.py, catalog_importer.py, cross-source matching, or Discogs fixtures.
---

# Discogs Ingestion

Spec: `base.md` §2 (metadata vs audio), §10, §16. Discogs is a **catalog source**, never an audio source and never a per-request dependency.

## 1. Before writing code (task P02.T01)

Read and summarize into `docs/data-sources.md`, with the date read:
- API Terms of Use, attribution requirements, caching/storage limits — https://www.discogs.com/developers and the linked terms.
- Current rate limits and auth rules from the docs (historically: authenticated ≈ 60 req/min, unauthenticated ≈ 25 req/min, moving 60-s window; headers `X-Discogs-Ratelimit`, `X-Discogs-Ratelimit-Used`, `X-Discogs-Ratelimit-Remaining`). **Verify — don't trust these numbers.**
- Discogs also publishes monthly XML data dumps. Note their license; they are an alternative for a bounded offline import, but the plan's default is the API with a scoped selection.

If the terms forbid something the plan assumes, stop and record it as a blocker.

## 2. Client design (`ingestion/discogs_client.py`)

```python
class DiscogsClient:
    def __init__(self, http: httpx.Client, *, user_agent: str, token: str | None,
                 limiter: RateLimiter, retry: RetryPolicy, clock: Clock, logger: Logger): ...
    def get_release(self, release_id: int) -> DiscogsRelease: ...
    def get_master(self, master_id: int) -> DiscogsMaster: ...
    def get_artist(self, artist_id: int) -> DiscogsArtist: ...
    def iter_artist_releases(self, artist_id: int, *, max_items: int) -> Iterator[DiscogsReleaseSummary]: ...
    def iter_label_releases(self, label_id: int, *, max_items: int) -> Iterator[DiscogsReleaseSummary]: ...
    def search(self, *, genre: str | None, style: str | None, type: str = "release", max_items: int) -> Iterator[DiscogsSearchHit]: ...
```

- **Headers:** always `User-Agent: {DISCOGS_USER_AGENT}` (required by Discogs; requests without one get rejected). Auth via `Authorization: Discogs token={DISCOGS_TOKEN}` when set. The token is read from settings, never logged (redact in request logs).
- **Rate limiting:** client-side token bucket sized from settings *and* adaptive to `X-Discogs-Ratelimit-Remaining`; on `429` sleep per `Retry-After` if present, else back off. Never parallelize requests to beat the limit.
- **Retries:** exponential backoff with jitter for `429`, `5xx`, timeouts, connection errors; max attempts configurable. No retry for `4xx` other than 429.
- **Error classification:** map to `DiscogsRateLimited`, `DiscogsUnavailable`, `DiscogsNotFound`, `DiscogsResponseInvalid`, `DiscogsAuthError`.
- **Validation:** parse JSON into raw Pydantic models (`DiscogsRelease`, … with `extra="ignore"`) in `ingestion/discogs_models.py`. Invalid payload → `DiscogsResponseInvalid`, never partial writes.
- **Pagination:** follow `pagination.urls.next` / `page`+`per_page` (`per_page` ≤ 100); always bounded by `max_items`.
- **Logging:** method, path, status, latency, remaining quota. One structured line per request.
- **Inject** `Clock`/sleep so tests run instantly.

## 3. Bounded importer (`ingestion/catalog_importer.py`, `scripts/import_discogs.py`)

Selection is a checked-in config, e.g. `config/discogs_selection.yaml`:

```yaml
selection_version: 1
max_releases: 500
seeds:
  - {kind: style, value: "Ambient", max_items: 100}
  - {kind: label, id: 12345, max_items: 50}
  - {kind: release, id: 249504}
```

- Importer is **idempotent**: deterministic internal IDs, upserts, `import_run` table with selection hash, started/finished timestamps, counts, errors.
- **Raw cache first:** persist raw JSON responses to `data/raw/discogs/{kind}/{id}.json` (git-ignored) and normalize from the cache. Re-normalization never re-hits the API.
- **Transactional:** a failed or interrupted run must not corrupt the catalog (write normalized records in a transaction per release; external failure ⇒ rollback that release only, log, continue).
- Store per base §10.2: release id, master id, artist/label ids, genres, styles, year, tracklist, source URL (`uri`), import timestamp.

## 4. Normalization (`ingestion/normalizer.py`)

- **Tracklist:** keep `position`, `title`, `duration`, per-track `artists`/`extraartists`. Skip entries whose `type_` is `heading`; expand `index` sub-tracks. Parse durations `"m:ss"` / `"h:mm:ss"` → seconds; empty → `None`.
- One `Track` per tracklist entry, linked to `release_id` and `master_release_id`. Do not dedupe versions across releases without evidence — record `TrackRelationship(type="same_master")` instead.
- **Artist names:** Discogs appends disambiguators like `"Name (2)"` and uses `anv` (name variation) and `join` strings. Keep the canonical name, store the stripped form for matching, preserve aliases/ANVs.
- Genres/styles are tags with `source="discogs"`; never infer instruments or moods from them.
- `discogs_url` is the `uri` returned by the API — never constructed by hand.

## 5. Relationship graph

Derive from normalized data only: `same_artist`, `same_label`, `same_master`, `same_release`, `shared_style` (weighted by tag rarity). Each edge carries `evidence_source`. These are **context, not audio similarity**.

## 6. FMA ↔ Discogs matching (`ingestion/matcher.py`)

Conservative, explainable, reversible:

1. Blocking: normalized artist name (casefold, NFKD, strip punctuation/disambiguator, "the" handling).
2. Candidate score from: exact normalized title match, artist match, duration within ±3 s (when both known), release title/year agreement.
3. Accept only if **title AND artist** match **and** at least one corroborating signal (duration or release), and there is exactly one candidate above threshold. Otherwise store as `unresolved` with the candidate list.
4. Store `CrossSourceMatch(fma_track_id, discogs_release_id, discogs_track_position, method, confidence, signals, decided_at)`.
5. Never merge on title or artist similarity alone (base §2, §10.4). Expect few matches for FMA — that is fine and must be reported.

## 7. Testing

- Record fixtures once (sanitized, small) into `tests/fixtures/discogs/*.json`; no token in fixtures. Check that the terms allow storing them; if unsure, hand-write minimal synthetic payloads with the same shape.
- Use `httpx.MockTransport` (or `respx`) — no live calls in the default test run. A single `@pytest.mark.live` smoke test may exist, skipped without `DISCOGS_TOKEN`.
- Must-have cases: 429 with/without `Retry-After`, 5xx then success, malformed JSON, pagination stop at `max_items`, heading/index tracklist entries, `"Name (2)"` artists, missing durations, ambiguous match stays unresolved.
