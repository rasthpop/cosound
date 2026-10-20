# Cosound: Semantic Music Discovery

Natural-language music discovery: a request such as *"something chill with a flute"* is interpreted, matched against a local catalog with hybrid retrieval (Discogs/FMA metadata + CLAP text-to-audio similarity), ranked, explained from evidence, and placed on a stable UMAP map of the catalog.

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
uv run python scripts/download_fma.py            # FMA metadata (checksum-verified)
uv run python scripts/import_fma.py              # tracks in data/evaluation/fma_20_manifest.csv
uv run python scripts/import_discogs.py          # bounded Discogs import (needs DISCOGS_TOKEN for style seeds)
uv run python scripts/build_relationships.py     # same artist/label/master/release, shared styles
uv run python scripts/match_sources.py           # conservative FMA <-> Discogs matching
uv run python scripts/catalog_stats.py           # summary; --lookup "flute" to search
```

Terms, licenses and the bounded-import procedure: [`docs/data-sources.md`](docs/data-sources.md).
The 20-track evaluation corpus and how to finish it: [`data/evaluation/README.md`](data/evaluation/README.md).

## Data

`data/raw`, `data/processed`, `data/embeddings`, `data/indexes` and `artifacts/` stay local and are git-ignored. Only the evaluation inputs in `data/evaluation/` are tracked. Audio files, model checkpoints and secrets are never committed.
