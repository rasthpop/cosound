# Implementation Phases — Semantic Music Discovery

Decomposition of `base.md` (functional plan) into executable phases and tasks, plus a provisional UI/UX track to be finalized when the separate UI/UX plan arrives.

- **How to execute:** load the `implementation-roadmap` skill; run `python skills/implementation-roadmap/scripts/phase_status.py`.
- **Task format & statuses:** see `skills/implementation-roadmap/SKILL.md`.

## Phase list

| Phase | Title | base.md | Milestone | Track |
|---|---|---|---|---|
| [P00](functional/P00-foundation.md) | Project foundation & tooling | §4, §15, §17 | — | functional |
| [P01](functional/P01-domain-model.md) | Domain model, protocols, persistence | §5, §16 | M1 | functional |
| [P02](functional/P02-catalog-ingestion.md) | Catalog ingestion: Discogs + FMA + matching | §2, §10, §12.1 | **M1** | functional |
| [P03](functional/P03-clap-semantic-retrieval.md) | CLAP embeddings & semantic retrieval | §7.2–7.3, §9 | **M2** | functional |
| [P04](functional/P04-hybrid-retrieval.md) | Hybrid retrieval, constraints, ranking, diversity | §7, §9.4 | **M3** | functional |
| [P05](functional/P05-evaluation-harness.md) | Evaluation harness & dev-split calibration | §12 | M3 (compare) | functional |
| [P06](functional/P06-agents.md) | Agents A/B/C, descriptions, sessions, orchestrator | §6, §7, §8 | **M4** | functional |
| [P07](functional/P07-spatial-pipeline.md) | UMAP spatial pipeline, map & neighbor services | §11, §13.4–13.5 | **M5** | spatial (parallel) |
| [P08](functional/P08-application-and-api.md) | Application services & FastAPI | §13, §16 | M6 (backend) | functional |
| [P09](functional/P09-frontend-integration-layer.md) | Frontend data layer: types, client, mocks, hooks | §14 | **M6** | functional ⇄ UI seam |
| [P10](functional/P10-final-evaluation-and-docs.md) | Final evaluation, hardening, documentation | §12, §17, §20 | **M7** | functional |
| [U00](ui/U00-ui-plan-intake.md) | UI/UX plan intake | UI plan | — | UI (blocked on plan) |
| [U01](ui/U01-design-foundation.md) | Design foundation: tokens, theme, workbench | UI plan | — | UI |
| [U02](ui/U02-presentational-components.md) | Presentational views & state variants | UI plan, §14.4 | — | UI |
| [U03](ui/U03-track-map-view.md) | deck.gl track map view | UI plan, §14.4 | — | UI |
| [U04](ui/U04-screen-composition.md) | Containers & screen composition | UI plan | — | UI |
| [U05](ui/U05-ux-quality-and-isolation.md) | UX quality, accessibility, isolation proof | UI plan, §1 req.10 | — | UI |

U-phases are **provisional**: their tasks describe the structure any UI plan will need. The `ui-plan-intake` skill rewrites them when the plan arrives.

## Dependency graph

```text
P00 ─► P01 ─► P02 ─► P03 ─┬─► P04 ─► P05 ─► P06 ─► P08 ─► P09 ─► P10
                          │                          ▲      │
                          └─► P07 (spatial) ─────────┘      │ (P09.T02 fixtures)
                                                            ▼
                         U00 (needs UI plan) ─► U01 ─► U02 ─┬─► U04 ─► U05
                                                    └► U03 ─┘    ▲
                                                                 └─ needs P09 hooks
```

Parallel tracks:
- **Spatial (P07)** only needs P03 (embeddings). It can proceed alongside P04–P06.
- **UI (U01–U03)** needs U00 (the UI plan) and the P09 contract fixtures (P09.T02) — **not** the running backend. P09.T01/T02 can be done early from the DTOs in P08.T02 to unblock UI work.
- **P10** waits for everything functional; U05 isn't required for the functional Definition of Done.

## Isolation rule between tracks

| Track | Writes to | Never writes to |
|---|---|---|
| functional (P) | `src/`, `scripts/`, `tests/`, `config/`, `data/evaluation/`, `docs/`, `frontend/src/api/`, `frontend/src/hooks/`, `frontend/src/mocks/`, `frontend/openapi.json` | `frontend/src/theme/`, `components/`, `pages/` |
| UI (U) | `frontend/src/theme/`, `components/`, `pages/`, `App.tsx`, `main.tsx`, `docs/ui/` | everything else — requests go through **contract-request tasks** appended to P08/P09 |

The seam is the hook return types and `frontend/src/api/types.ts` (generated from OpenAPI). Enforced by `skills/music-discovery-architecture/scripts/check_boundaries.py`.

## Milestone → acceptance (base §18)

| Milestone | Acceptance criterion | Verified by |
|---|---|---|
| M1 | local catalog queryable without live Discogs | P02 exit |
| M2 | text query retrieves ranked candidates from local audio corpus | P03 exit |
| M3 | metadata-only, CLAP-only, hybrid run on the same catalog and can be compared | P04 exit + P05 exit |
| M4 | NL request → ranked plate; feedback changes next plate predictably | P06 exit |
| M5 | stable map coordinates, no UMAP during search | P07 exit |
| M6 | interface can search, show plate, give feedback, get map points with no ML/retrieval logic | P09 exit |
| M7 | a new developer reproduces the evaluation and understands each component | P10 exit |

## Definition of Done (base §20) → where it's satisfied

| DoD item | Task(s) |
|---|---|
| Bounded, documented Discogs import | P02.T04 |
| Reproducible FMA load | P02.T06, P02.T10 |
| Cross-source matching with provenance/uncertainty | P02.T08 |
| Versioned CLAP embeddings | P03.T02, P03.T04 |
| Metadata & semantic retrieval independent | P03.T07, P04.T01 |
| Safe hybrid ranking | P04.T05 |
| Hard constraints independent of soft ranking | P04.T04 |
| Agent A validated specs | P06.T02 (LLM path: P06.T03, model choice P06.T12) |
| Agent B ranked, deduped, diverse | P06.T04 |
| Agent C state updates + grounded descriptions | P06.T05, P06.T08 |
| UMAP persisted outside request path | P07.T02, P07.T03 |
| Map API without deck.gl dependency | P07.T05, P08.T06 |
| API: search, details, feedback, map | P08.T04–T06 |
| Hooks isolate API from views | P09.T04–T07 |
| 20-example comparison of three systems | P05.T05, P10.T02 |
| Evaluation artifacts + limitations report | P10.T05 |
| Tests cover principal contracts | every phase; audited in P10.T07 |
| No keys, unlicensed audio, fabricated links, unsupported claims | P00.T01, P02.T01, P10.T04, P10.T07 |

## Supporting skills & agents

Skills (`skills/`): `implementation-roadmap`, `music-discovery-architecture`, `domain-modeling`, `discogs-ingestion`, `fma-audio-corpus`, `clap-embeddings`, `hybrid-retrieval`, `agent-orchestration`, `openrouter-llm`, `grounded-explanations`, `umap-spatial-projection`, `api-contracts`, `retrieval-evaluation`; UI: `ui-architecture`, `ui-plan-intake`, `ui-design-tokens`, `deckgl-track-map`, `ux-states-and-evidence`, `ui-isolated-development`.

Agents (`.claude/agents/`): `backend-implementer`, `ui-implementer`, `architecture-reviewer`, `api-contract-guardian`, `evidence-auditor`.
