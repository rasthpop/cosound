# P00 — Project Foundation & Tooling

**Goal:** a repository where every later task can be implemented, tested, linted, and boundary-checked from day one, with no secrets or data committed.
**base.md:** §4 (structure), §15 (config & secrets), §17 (testing), §3 (rules).
**Depends on:** —

### P00.T01 — Repository scaffold & hygiene
- **Skills:** music-discovery-architecture
- **Depends on:** —
- **Files:** pyproject.toml, README.md, .gitignore, .env.example, src/music_discovery/__init__.py, config/.gitkeep, data/{raw,processed,embeddings,indexes,evaluation}/.gitkeep, artifacts/{umap,evaluation}/.gitkeep, docs/
- **Do:**
  - `uv init`-style `pyproject.toml` (Python ≥ 3.11, src layout, package `music_discovery`), dev deps: pytest, pytest-cov, ruff, mypy, hypothesis, import-linter.
  - `.gitignore`: `.env`, `data/llm_cache/`, `data/raw/`, `data/processed/`, `data/embeddings/`, `data/indexes/`, `artifacts/**` except `.gitkeep`, `*.mp3`, `*.wav`, `*.pt`, `*.npy`, `node_modules/`, `*.db`. Keep `data/evaluation/` tracked.
  - `.env.example` exactly as base §15 plus the OpenRouter keys from the `openrouter-llm` skill (`LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY=`, `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`, `LLM_MODEL=`, `LLM_FALLBACK_MODELS=`, `LLM_TIMEOUT_S=`), `ACTIVE_EMBEDDING_VERSION=`, `ACTIVE_PROJECTION_VERSION=`, `API_CORS_ORIGINS=`.
  - README: purpose, pointers to `base.md`, `skills/phases/README.md`, setup commands.
  - Move `base.md` to `docs/base.md` **only if** the user agrees; otherwise leave it and reference it as is.
- **Done when:**
  - `uv sync` succeeds; `uv run python -c "import music_discovery"` works.
  - `git check-ignore data/raw/x.mp3 .env` reports both ignored.
- **Status:** [x]

### P00.T02 — Settings module
- **Skills:** music-discovery-architecture
- **Depends on:** P00.T01
- **Files:** src/music_discovery/infrastructure/settings.py, tests/unit/infrastructure/test_settings.py
- **Do:**
  - `pydantic-settings` `Settings` with every `.env.example` key, typed paths (`DATA_DIR`, `ARTIFACTS_DIR` resolved relative to repo root), `SecretStr` for tokens, `APP_ENV` enum.
  - `get_settings()` factory (no module-level instance). Derived helpers: `embeddings_dir`, `umap_dir`, `evaluation_dir`.
  - A `redacted()` dump for logging/meta files (secrets masked).
- **Done when:**
  - Tests: defaults load, env override works, secrets never appear in `redacted()` or `repr`.
- **Status:** [x]

### P00.T03 — Quality gates & boundary enforcement
- **Skills:** music-discovery-architecture
- **Depends on:** P00.T01
- **Files:** Makefile (or justfile), .importlinter (or [tool.importlinter] in pyproject), .pre-commit-config.yaml, .github/workflows/ci.yml, pyproject.toml ([tool.ruff], [tool.mypy], [tool.pytest.ini_options])
- **Do:**
  - Targets: `make lint` (ruff), `make type` (mypy; strict for domain/retrieval/agents/application), `make test` (`pytest -m "not slow and not live"`), `make boundaries` (`python skills/music-discovery-architecture/scripts/check_boundaries.py`), `make check` = all.
  - pytest markers: `unit, integration, api, evaluation, slow, live`.
  - import-linter "layers" + "forbidden" contracts mirroring the architecture skill table.
  - CI runs `make check` on push/PR (Python + Node jobs; Node job added in P00.T04).
  - Pre-commit: ruff, ruff-format, a secrets scanner (e.g. `detect-secrets` or `gitleaks`), check-added-large-files.
- **Done when:**
  - `make check` passes on the empty scaffold.
  - Adding a deliberate violation (e.g. `import fastapi` in `domain/`) makes `make boundaries` fail; remove it afterwards.
- **Status:** [x]

### P00.T04 — Frontend skeleton (data layer folders only)
- **Skills:** ui-architecture, ui-isolated-development
- **Depends on:** P00.T01
- **Files:** frontend/package.json, frontend/tsconfig.json, frontend/vite.config.ts, frontend/.eslintrc.* (or eslint.config.js), frontend/src/{api,hooks,mocks}/README.md, frontend/src/{theme,components,pages}/README.md, frontend/src/main.tsx, frontend/src/App.tsx
- **Do:**
  - Vite + React + TypeScript (strict), vitest + Testing Library + MSW installed; path alias `@/` → `src/`.
  - ESLint `no-restricted-imports` rules mirroring the TS table in the architecture skill (components ✗ hooks/api client; deck.gl only in components/map).
  - Each folder README states its owner (functional vs UI track) and import rules. `theme/`, `components/`, `pages/` contain only README (UI plan fills them).
  - `App.tsx` renders nothing meaningful (a placeholder text) — no styling decisions.
  - Scripts: `dev`, `dev:mock`, `build`, `test`, `lint`, `typecheck`, `contract:check` (stub until P09.T01).
  - Add Node job to CI: `npm ci && npm run lint && npm run typecheck && npm run test`.
- **Done when:**
  - `npm run build`, `npm run test`, `npm run lint` pass; `check_boundaries.py --only ts` passes.
- **Status:** [x]

### P00.T05 — Architecture decision records
- **Skills:** music-discovery-architecture
- **Depends on:** P00.T01
- **Files:** docs/adr/0000-template.md, docs/adr/0001-stack.md
- **Do:**
  - ADR-0001 records: Python/uv, FastAPI, Pydantic v2, SQLite + SQLAlchemy 2.x Core behind repository protocols, NumPy exact cosine index (FAISS optional), BM25/FTS5 for lexical search, laion_clap vs transformers (deferred to ADR-0002 in P03.T01), umap-learn, **OpenRouter free models** (https://openrouter.ai/collections/free-models) as the optional LLM provider for the agents via an OpenAI-compatible adapter (specific models chosen in P06.T12), React+TS+Vite, deck.gl (UI track), openapi-typescript, MSW.
  - Each decision: context, decision, consequences, reversible-by.
- **Done when:**
  - ADR-0001 merged; any user-overridden choices reflected.
- **Notes:** ADR-0001 written with status "Proposed"; switch it to "Accepted" after review.
- **Status:** [x]

### P00.T06 — Test infrastructure & fakes package
- **Skills:** music-discovery-architecture, domain-modeling
- **Depends on:** P00.T03
- **Files:** tests/conftest.py, tests/{unit,integration,api,evaluation}/__init__.py, tests/fakes/__init__.py, tests/fixtures/README.md
- **Do:**
  - Shared fixtures: temp `DATA_DIR`/`ARTIFACTS_DIR`, settings override, frozen clock, deterministic id generator.
  - `tests/fixtures/README.md`: what may be stored (small synthetic/sanitized data only; licensing note).
  - `slow`/`live` markers skipped by default; `--run-slow` option.
- **Done when:**
  - `make test` runs and reports 0 failures; `pytest --run-slow` selects slow tests.
- **Status:** [x]

## Exit criteria
- [x] `make check` and frontend `npm run lint && npm run test` green (verified locally; the CI workflow runs the same commands and first runs on push).
- [x] Boundary checker wired and demonstrably failing on violations.
- [x] No secrets, audio or large artifacts tracked (`git ls-files` audit).
