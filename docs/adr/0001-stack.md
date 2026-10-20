# ADR-0001: Core technology stack

- **Status:** Proposed (awaiting review)
- **Date:** 2026-10-20
- **Phase/Task:** P00.T05

## Context

`base.md` §4 asks for a Python backend and ML pipeline with FastAPI, a TypeScript frontend integration layer, and a deck.gl map. §3 requires deterministic, testable services behind explicit boundaries, so every heavy dependency must sit behind a domain protocol. The prototype catalog is small (20 evaluation tracks, a bounded Discogs import), so exact search and a single-file database are enough. Exact versions are pinned by `uv.lock` and `frontend/package-lock.json`.

## Decisions

| Area | Choice | Behind which boundary |
|---|---|---|
| Python | 3.11+ (developed on 3.12), `uv` for environments and locking | — |
| Validation & schemas | Pydantic v2, `pydantic-settings` for configuration | `domain/`, `infrastructure/settings.py` |
| API | FastAPI + Uvicorn | `api/` only |
| Persistence | SQLite via SQLAlchemy 2.x Core | repository protocols in `domain/protocols.py`, implementations in `infrastructure/` |
| Vector search | NumPy exact cosine (`NumpyCosineIndex`); FAISS `IndexFlatIP` as an optional drop-in | `VectorIndex` protocol |
| Lexical search | SQLite FTS5 or in-memory BM25 (chosen in P04.T01) | `LexicalIndex` protocol |
| Audio embeddings | LAION CLAP; checkpoint and package (`laion_clap` vs `transformers`) decided in ADR-0002 (P03.T01) | `AudioEncoder` / `TextEncoder` protocols, `audio/` only |
| Projection | `umap-learn`, seeded, offline only | `spatial/`, called from `scripts/build_map.py` |
| Agent LLMs (optional) | OpenRouter free models (https://openrouter.ai/collections/free-models) through an OpenAI-compatible adapter; models chosen in ADR-0004 (P06.T12) | `StructuredLLM` protocol, `infrastructure/llm.py` |
| Quality gates | ruff (lint + format), mypy strict, pytest (+ hypothesis), import-linter, `check_boundaries.py`, pre-commit with local hooks, detect-secrets | `make check`, CI |
| Frontend | React + TypeScript (strict) + Vite, Vitest + Testing Library + jsdom, MSW for contract mocks, ESLint flat config with import restrictions | `frontend/src/{api,hooks,mocks}` (functional track) |
| API types | `openapi-typescript` generated from the backend OpenAPI export (P09.T01) | `frontend/src/api/generated.ts` |
| Map rendering | deck.gl `ScatterplotLayer` + `OrthographicView` (UI track) | `frontend/src/components/map/` only |

## Consequences

- No heavy ML dependency is installed until the phase that needs it (CLAP in P03, UMAP in P07), so early phases stay fast to install and test.
- Swapping SQLite, the vector index, the LLM provider or the CLAP package touches one `infrastructure/` or `audio/` module and its tests; services depend only on protocols.
- SQLite limits concurrent writers. That is acceptable for a single-process prototype; a server database would only need a new repository implementation.
- Free OpenRouter models change over time and have usage limits. Every LLM path therefore has a deterministic fallback, and model IDs live in configuration.

## Reversible by

Each row's boundary column names the interface that contains the change. Replacing a choice means adding an implementation behind that interface, running the contract tests for it, and updating this ADR with a superseding one.
