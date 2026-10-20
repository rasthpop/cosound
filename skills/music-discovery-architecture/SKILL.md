---
name: music-discovery-architecture
description: Layer map, dependency rules and placement guide for the semantic music discovery system (backend Python package `music_discovery` + `frontend/`). Load before creating or moving any module, adding a dependency/import, wiring services together, or reviewing a change for boundary violations. Includes the runnable boundary checker.
---

# Music Discovery — Architecture & Boundaries

Source of truth: `base.md` §3, §4, §14. This skill turns those rules into checkable constraints.

## 1. The one principle

> The hybrid engine decides relevance. Agents coordinate. UMAP supplies coordinates.
> The interface only presents data and emits user actions.

Every placement decision follows from that sentence.

## 2. Backend layers (`src/music_discovery/`)

| Layer | Owns | May import (internal) | Heavy third-party allowed |
|---|---|---|---|
| `domain/` | models, Pydantic schemas, errors, `Protocol`s (repositories, encoders, vector index, LLM, clock) | nothing | pydantic, numpy (types only) |
| `infrastructure/` | SQL repositories, vector index, settings, LLM client adapter (OpenRouter, OpenAI-compatible) | `domain` | sqlalchemy/sqlite3, faiss, anthropic/openai, httpx |
| `ingestion/` | Discogs client, FMA loader, normalizer, importer, cross-source matcher | `domain` | httpx/requests, pandas |
| `audio/` | CLAP encoder, embedding store, acoustic features | `domain` | torch, laion_clap, transformers, librosa, soundfile |
| `retrieval/` | metadata/semantic/relationship retrievers, merger, normalizer, constraints, ranker, MMR | `domain` | numpy |
| `descriptions/` | evidence builder, description service, claim validator | `domain` | — |
| `spatial/` | feature builder, UMAP projector, spatial repository logic, neighbor service | `domain` | umap, scikit-learn |
| `agents/` | Agent A/B/C + orchestrator, deterministic parser, lexicon | `domain`, `retrieval`, `descriptions` | — (LLM only via `domain.protocols.StructuredLLM`) |
| `application/` | use-case services: search, feedback, track, map | `domain`, `agents`, `retrieval`, `descriptions`, `spatial` | — |
| `evaluation/` | dataset loaders, metrics, baseline runners, report writers | `domain`, `retrieval`, `agents`, `descriptions`, `spatial` | pandas |
| `api/` | FastAPI app, routes, request/response DTO mapping | `domain`, `application` (+ anything in `api/dependencies.py`, `api/app.py` = composition root) | fastapi, starlette, uvicorn |

Rules that the table implies:

- **Dependency direction is inward.** Nothing imports `api`. Only composition roots (`api/dependencies.py`, `api/app.py`, `scripts/*.py`, tests) construct concrete infrastructure.
- **Services receive collaborators through constructor injection** typed by `domain.protocols`. No module-level singletons that load models or open DBs at import time.
- **Agents never touch data.** An agent that needs tracks calls a retrieval service; an agent that needs an LLM receives a `StructuredLLM`.
- **Retrieval works without an LLM** and without `agents/` (baselines in `retrieval-evaluation` call it directly).
- **Search must work when CLAP, the LLM, or the UMAP artifact is unavailable** — each is an optional collaborator with an explicit "unavailable" status, never a crash.
- **UMAP never runs in the request path.** `spatial/umap_projector.py` is called only from `scripts/build_map.py`.

## 3. Frontend layers (`frontend/src/`)

| Layer | Owner | May import | Notes |
|---|---|---|---|
| `api/` (`client.ts`, `types.ts`, `generated.ts`) | functional plan | `api` | the only place `fetch` exists |
| `hooks/` | functional plan | `api`, `hooks`, react | no deck.gl, no components, no styling |
| `mocks/` | functional plan | `api`, `mocks` | fixtures + MSW handlers mirroring the OpenAPI contract |
| `theme/` | UI plan | `theme` | design tokens only |
| `components/` | UI plan | `components`, `theme`, `api/types`, `api/generated` (types) | pure views: props in, events out |
| `components/map/` | UI plan | as above + `@deck.gl/*` | the only place deck.gl may appear |
| `pages/` | UI plan | `pages`, `hooks`, `components`, `theme`, `api/types` | containers: wire hooks → views |
| root (`main.tsx`, `App.tsx`) | shared | anything | composition root |

The functional/UI seam is **the hook return types + `api/types.ts`**. The UI plan may change everything in `theme/`, `components/`, `pages/` without touching backend or hooks. If a view needs data the hooks don't expose, change the API contract (see `api-contracts`) — never compute it in a view.

## 4. Checking the boundaries

```bash
python skills/music-discovery-architecture/scripts/check_boundaries.py          # whole repo
python skills/music-discovery-architecture/scripts/check_boundaries.py --root . --only python
```

The script parses Python imports with `ast` and TS/TSX imports with regexes, applies the tables above, and exits non-zero on violations. Missing directories are skipped, so it is safe from Phase P00 onward. Wire it into `make check` / CI in P00. When a rule must legitimately change, edit the tables at the top of the script **and** this file in the same commit, with the reason in the commit message.

Complementary static tooling (set up in P00): `import-linter` contracts for Python, `eslint` `no-restricted-imports` for TS. The script is the source of truth; linters are convenience.

## 5. Where does X go?

| Thing | Location |
|---|---|
| A new score signal | `retrieval/` service + config weight; surfaced in `ScoreBreakdown` |
| Synonym / mood lexicon | `agents/lexicon/*.yaml` (data, versioned) |
| Discogs HTTP detail | `ingestion/discogs_client.py` only |
| CLAP checkpoint loading | `audio/clap_encoder.py` only |
| Text formatting of a score for humans | the view (`components/`), from raw API values |
| Deciding *whether* a claim is allowed | `descriptions/` validator — never the UI |
| Session/feedback persistence | repository protocol in `domain`, SQL impl in `infrastructure` |
| Paths, model names, weights | `infrastructure/settings.py` (pydantic-settings) + `.env` / config files |

## 6. Conventions

- Python ≥ 3.11, `uv` for env, `ruff` (lint+format), `mypy --strict` on `domain`, `retrieval`, `agents`, `application`.
- `pytest` with markers `unit`, `integration`, `api`, `evaluation`, `slow` (CLAP/UMAP real models). Unit tests use fakes from `tests/fakes/` implementing `domain.protocols`.
- Every persisted artifact (embeddings, index, projection, evaluation run) carries a `*.meta.json` with model/config versions and a content hash.
- No hard-coded paths; everything resolves from `DATA_DIR` / `ARTIFACTS_DIR` settings.
- Missing ≠ zero. Optional values stay `None` end-to-end (see `domain-modeling`).
