# Implementation Skills, Agents & Phase Plans

Everything needed to implement `base.md` (functional system) and, later, the UI/UX plan.
`.claude/skills` is a symlink to this folder, so Claude Code discovers these skills automatically.

## Start here
1. `skills/phases/README.md` — phase list, dependency graph, milestone mapping, track isolation.
2. `python skills/implementation-roadmap/scripts/phase_status.py` — progress and next ready tasks.
3. Load `implementation-roadmap` at the start of every implementation session.

## Skills

### Functional
| Skill | Use for |
|---|---|
| `implementation-roadmap` | session protocol, task format, status tracking, plan changes (+ `scripts/phase_status.py`) |
| `music-discovery-architecture` | layer map, dependency rules, placement (+ `scripts/check_boundaries.py`) |
| `domain-modeling` | entities, SearchSpecification, evidence/score schemas, protocols, errors, missing ≠ zero |
| `discogs-ingestion` | Discogs client, bounded importer, normalization, relationships, FMA↔Discogs matching |
| `fma-audio-corpus` | FMA metadata/audio loading, licenses, 20-track manifest |
| `clap-embeddings` | checkpoint choice, encoder, versioned embedding store, vector index, semantic retriever |
| `hybrid-retrieval` | metadata retrieval, merge, normalization, hard constraints, ranker, MMR, modes |
| `agent-orchestration` | Agents A/B/C, lexicon parser, optional LLM with fallback, feedback rules, sessions |
| `openrouter-llm` | LLM provider for the agents: OpenRouter free models (https://openrouter.ai/collections/free-models), adapter, fallbacks, limits, data policy |
| `grounded-explanations` | evidence → descriptions, allowed claims, claim validator |
| `umap-spatial-projection` | offline UMAP, persistence/validation, quality, map & neighbor services |
| `api-contracts` | FastAPI DTOs, error envelope, OpenAPI → TS types, fixtures, contract-change procedure |
| `retrieval-evaluation` | queries, judgments, split, metrics, baselines, report |

### UI/UX
| Skill | Use for |
|---|---|
| `ui-plan-intake` | turning the forthcoming UI/UX plan into U-phases + contract requests |
| `ui-architecture` | View / Hook / Container pattern, folder & import contract, state ownership |
| `ui-design-tokens` | token tiers, themes/atmospheres, map scales, a11y baselines |
| `deckgl-track-map` | OrthographicView + ScatterplotLayer renderer, picking, fallbacks |
| `ux-states-and-evidence` | full state matrix, honest presentation of scores/evidence, feedback UX |
| `ui-isolated-development` | MSW fixtures, workbench, vitest/Playwright/axe, isolation proof |

Also useful (global): `dataviz` (map color scales).

## Agents (`.claude/agents/`)
| Agent | Role |
|---|---|
| `backend-implementer` | implements one P-task; never touches the visual layer |
| `ui-implementer` | implements one U-task inside `theme/`, `components/`, `pages/` only |
| `architecture-reviewer` | read-only boundary/layering review (runs the checker) |
| `api-contract-guardian` | OpenAPI ⇄ TS types ⇄ fixtures sync, breaking-change scan |
| `evidence-auditor` | audits descriptions, copy, fixtures for unsupported claims |

## Tools
- `music-discovery-architecture/scripts/check_boundaries.py` — Python (ast) + TS import rules; exit 1 on violations.
- `implementation-roadmap/scripts/phase_status.py` — progress, ready tasks, `--check` dependency validation.

## Phase plans
- `phases/functional/P00…P10` — backend, ML pipeline, API, frontend data layer (base.md milestones M1–M7).
- `phases/ui/U00…U05` — provisional UI track; rewritten by `ui-plan-intake` when the UI/UX plan arrives.
