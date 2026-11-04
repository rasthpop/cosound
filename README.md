# Cosound: Semantic Music Discovery

Natural-language music discovery: a request such as *"something chill with a flute"* is interpreted, matched against a local catalog with hybrid retrieval (FMA metadata + CLAP text-to-audio similarity), ranked, explained from evidence, and placed on a stable UMAP map of the catalog.

- Functional specification: [`base.md`](base.md) (the OG implementation plan)
- Implementation plan and progress: [`skills/phases/README.md`](skills/phases/README.md)
- Architecture rules: [`skills/music-discovery-architecture/SKILL.md`](skills/music-discovery-architecture/SKILL.md)

## Setup

```bash
uv sync                      # Python env + dev tools
cp .env.example .env         # then fill in tokens locally; never commit .env
(cd frontend && npm ci)      # frontend data layer + tooling
uv run pre-commit install    # optional: local git hooks
```

## Run the app locally

You need Python 3.11+, [uv](https://docs.astral.sh/uv/) and Node 22+. Do the [Setup](#setup) steps first.

### Quick look: interface only

This needs no backend or data. The interface runs on mock data at http://localhost:5173:

```bash
cd frontend && npm run dev:mock
```

### Full app

**1. Build the data once.** The downloads need several GiB of disk, and embeddings can take a long time on a CPU.

```bash
uv run python scripts/download_fma.py --subset metadata --subset small
uv run python scripts/import_fma.py --subset small
uv run python scripts/build_relationships.py
uv run python scripts/fetch_clap_model.py     # the pinned CLAP checkpoint
uv run python scripts/build_embeddings.py     # audio embeddings for sound search
uv run python scripts/build_indexes.py        # validates the vector index
uv run python scripts/build_map.py            # the UMAP track map
```

The API uses the newest embeddings and map, unless `ACTIVE_EMBEDDING_VERSION` or `ACTIVE_PROJECTION_VERSION` in `.env` pins one. For a quick trial, `build_embeddings.py --limit 50` embeds only 50 tracks.

**2. Start the API** in one terminal. It runs on http://127.0.0.1:8000, with API docs at `/docs`.

```bash
make serve
```

**3. Start the interface** in a second terminal, then open http://localhost:5173. `API_PROXY_TARGET` is required: without it, the interface can't reach the API.

```bash
cd frontend && API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev
```

**4. Check what is available:**

```bash
curl http://127.0.0.1:8000/api/health
```

`capabilities` shows the state of `semantic`, `map` and `llm_interpreter`. The app still runs when one is missing: without embeddings, search uses metadata only, and `semantic_reason` and `map_reason` say what is missing.

### Optional: use an LLM

Without an LLM, queries are read by the deterministic parser. To have an [OpenRouter](https://openrouter.ai/collections/free-models) free model read them too, set these in `.env` and restart the API, choosing models from [`config/llm.yaml`](config/llm.yaml):

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=...
LLM_MODEL=...
LLM_FALLBACK_MODELS=...
```

This sends your query text to OpenRouter. Free models have low daily limits, so when one fails or hits a limit, search falls back to the parser and keeps working. LLM-first search is still in progress: for now the LLM doesn't choose the results. See [ADR-0007](docs/adr/0007-llm-first-search.md).

## Everyday commands

```bash
make check        # lint + types + tests + architecture boundaries
make test         # fast tests (slow/live tests are skipped)
make boundaries   # layer/import rules for backend and frontend
python skills/implementation-roadmap/scripts/phase_status.py   # plan progress
```

Frontend: `cd frontend && npm run lint && npm run typecheck && npm run test`.

## Building the local catalog

```bash
uv run python scripts/download_fma.py --subset metadata --subset small   # ~7.6 GiB, checksum-verified
uv run python scripts/import_fma.py --subset small   # the MVP catalog: 8,000 tracks, audio validated
uv run python scripts/build_relationships.py         # same artist / same album
uv run python scripts/catalog_stats.py               # summary; --lookup "flute" to search
```

The MVP is FMA-only ([ADR-0005](docs/adr/0005-fma-only-mvp.md)). Discogs support (`import_discogs.py`, `match_sources.py`) is built but deferred.
Terms, licenses and the bounded-import procedure: [`docs/data-sources.md`](docs/data-sources.md).
The 20-track evaluation corpus and how to finish it: [`data/evaluation/README.md`](data/evaluation/README.md).

## Data

`data/raw`, `data/processed`, `data/embeddings`, `data/indexes` and `artifacts/` stay local and are git-ignored. Only the evaluation inputs in `data/evaluation/` are tracked. Audio files, model checkpoints and secrets are never committed.
