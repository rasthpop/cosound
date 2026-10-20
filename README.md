# Semantic Music Discovery

Natural-language music discovery: a request such as *"something chill with a flute"* is interpreted, matched against a local catalog with hybrid retrieval (Discogs/FMA metadata + CLAP text-to-audio similarity), ranked, explained from evidence, and placed on a stable UMAP map of the catalog.

- Functional specification: [`base.md`](base.md)
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

## Data

`data/raw`, `data/processed`, `data/embeddings`, `data/indexes` and `artifacts/` stay local and are git-ignored. Only the evaluation inputs in `data/evaluation/` are tracked. Audio files, model checkpoints and secrets are never committed.
