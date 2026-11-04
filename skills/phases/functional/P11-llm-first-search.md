# P11 — LLM-First Query Parsing & Retrieval Selection

**Goal:** the LLM does the work on every search. It reads the query, decides what to search for, and chooses and orders the tracks returned from the dataset. This reverses "LLM paths stay disabled by default" (ADR-0004, decision 1).
**base.md:** §3, §6, §7, §19; deviates from the "primarily deterministic" wording in §6–7 (recorded in ADR-0007, P11.T01).
**Depends on:** P06, P08, P09. **P10 waits for this phase**, because the final evaluation must measure the system that ships.

## Design

```text
query ─► LLM reads the query and plans the search (call 1)
              │  validated: preferences, hard constraints, CLAP prompts
              ▼
         hybrid engine runs the plan over all 8,000 tracks
              │  BM25 + CLAP, hard constraints enforced, duplicates dropped
              ▼
         bounded shortlist (default 30 tracks, facts only)
              ▼
         LLM chooses and orders tracks from the shortlist (call 2)
              │  validated: only shortlist tracks, no invented entries
              ▼
         results + existing evidence-based match reasons
```

Fixed decisions, each with its reason:

- **The LLM never reads the catalog directly.** Audio similarity comes from CLAP, because the LLM can't hear audio. Sending 8,000 tracks is a catalog dump (CLAUDE.md non-negotiable) and does not fit a free model's limits. The shortlist is what makes LLM selection possible.
- **Two calls, no tool loop.** A free-running tool-calling agent would use an unbounded share of the free-tier quota per search, and base §19 rules out autonomous loops.
- **Hard constraints stay enforced in code.** The shortlist is built after constraint filtering, so the LLM can't return a track that violates one or an excluded track.
- **The LLM's output never becomes a claim about a track.** Selection returns ordered aliases only, with no free text. Match reasons still come from `descriptions/`.
- **Deterministic paths stay as the fallback.** Free models fail, rate-limit and disappear. A fallback is always labelled in the response, never passed off as an LLM result.
- **`HybridRetriever` stays LLM-free.** The LLM calls live in `agents/`, so baselines and boundary rules still hold.

Out of scope: Agent C stays code-only (P11.T03 keeps its LLM off), and description phrasing stays off (ADR-0004, decision 3).

### P11.T01 — ADR-0007: LLM-first search, and owner decisions
- **Skills:** openrouter-llm, music-discovery-architecture
- **Depends on:** —
- **Files:** docs/adr/0007-llm-first-search.md, docs/adr/0004-llm-models.md, CLAUDE.md, skills/openrouter-llm/, skills/agent-orchestration/, skills/hybrid-retrieval/, skills/music-discovery-architecture/
- **Owner:** human-in-the-loop (policy and account decisions)
- **Do:**
  - Write ADR-0007 superseding ADR-0004 decision 1, with this phase's design and its deviation from base §6–7.
  - Owner confirms: (a) a bounded shortlist of track facts may be sent to the LLM; (b) which daily quota the system is sized for; (c) `LLM_DATA_COLLECTION` stays `deny`.
  - Owner closes the open ADR-0004 item: check each chosen model's data policy and block training providers in the OpenRouter account.
  - Reword the CLAUDE.md rule to state what is allowed: a bounded per-search shortlist is permitted; catalog dumps, secrets and user or session identifiers remain forbidden.
  - Update the "hybrid engine decides relevance", "Agent B uses no LLM" and "LLMs are optional" wording in the listed skills. The agreed rule is that the engine produces the shortlist and the LLM chooses from it.
- **Done when:**
  - ADR-0007 is accepted by the owner with all three decisions recorded, and the data-policy item is ticked.
- **Status:** [x]
- **Notes:** Numbered ADR-0007 because ADR-0006 is CRISP-DM. Owner chose the shortlist, the free tier (50 requests/day) and `deny`, and confirmed the data policy (2026-11-04; not independently verified). The ADR records that fallback becomes a normal path at this quota.

### P11.T02 — Paraphrase query set for a fair comparison
- **Skills:** retrieval-evaluation, agent-orchestration
- **Depends on:** P11.T01
- **Files:** data/evaluation/llm_dev_queries.jsonl, data/evaluation/README.md
- **Do:**
  - Add dev-only queries using wording outside the lexicon (for example "get rid of the vocals", "something for a rainy night drive"), with expected attributes and hard constraints.
  - The parser's 1.000 F1 comes from a lexicon written against the same labels, so it shows consistency and not generalization (ADR-0004). This set measures generalization.
  - Write the labels before any model output is seen. Never derive anything from the test split.
- **Done when:**
  - At least 20 owner-reviewed queries exist, and the checked-in set is dated before the first P11.T04 model run.
- **Status:** [ ]

### P11.T03 — Per-task switches, search budget and caching
- **Skills:** openrouter-llm, music-discovery-architecture
- **Depends on:** P11.T01
- **Files:** src/music_discovery/infrastructure/settings.py, src/music_discovery/infrastructure/llm.py, src/music_discovery/api/dependencies.py, .env.example, tests/unit/infrastructure/test_llm.py, tests/unit/infrastructure/test_settings.py
- **Do:**
  - Add `LLM_QUERY`, `LLM_SELECTION` (default true) and `LLM_FEEDBACK` (default false). Today `build_llm` passes one client to the feedback normalizer, so enabling the provider would also enable the feedback LLM; `LLM_FEEDBACK=false` must prevent that.
  - Add `LLM_SEARCH_BUDGET_S` (default 15) as a deadline across the whole model chain and both calls. Today one call can retry at 20 s per attempt, per model, which is far too slow for a search.
  - Add `selection` to `DEFAULT_MAX_TOKENS` and `LLM_MODEL_SELECTION` as a per-task model.
  - Turn on a size-bounded response cache for the API under `data/llm_cache/` (git-ignored), so repeated searches spend no quota. Cache entries hold no user or session identifiers.
  - At 50 requests/day (ADR-0007) the daily limit is routine. When a 429 shows the daily quota is used up (`X-RateLimit-*` headers), stop retrying and go straight to the fallback until it resets.
- **Done when:**
  - Tests cover: feedback gets no client unless enabled; the deadline stops the chain and returns an error result; a cache hit makes no HTTP call; a used-up daily quota makes no further calls. The default test suite still makes no network calls.
- **Status:** [x]
- **Notes:** `generate(timeout_s=…)` is now a deadline for the whole call, defaulting to `LLM_SEARCH_BUDGET_S`. Sharing it across both calls is done in P11.T07, since the second call doesn't exist yet. Also stopped remembering a failed `GET /models`, which permanently downgraded models to prompt-only JSON. The API cache is `data/llm_cache/api/`, so pruning never touches evaluation responses. Daily-quota detection is tested against mocked `X-RateLimit-*` headers only; check the real format in P11.T04.

### P11.T04 — Model re-check and first real measurement
- **Skills:** openrouter-llm, retrieval-evaluation
- **Depends on:** P11.T01, P11.T02
- **Files:** config/llm.yaml, docs/adr/0007-llm-first-search.md, scripts/llm_model_check.py
- **Do:**
  - The shortlist dates from 2026-10-23 and `--evaluate` has never been run. Re-check the list, then run the current query prompt on the dev queries and the paraphrase set next to the parser, with caching on and within the daily quota.
  - At 50 requests/day this spans several days, so compare one or two models and let the cache carry progress between days.
  - Choose per-task chains from the results. Model IDs go in config only. A model not listed in ADR-0004 goes back to the owner for a data-policy check first.
- **Done when:**
  - ADR-0007 has the measured table with model IDs and dates: validity, attribute F1, hard-constraint accuracy, p50/p95 latency. `llm_model_check.py --strict` passes.
- **Status:** [ ]

### P11.T05 — LLM-first query interpretation (Agent A)
- **Skills:** agent-orchestration, openrouter-llm, domain-modeling
- **Depends on:** P11.T03, P11.T04
- **Files:** src/music_discovery/agents/agent_a_query.py, src/music_discovery/agents/llm_query_interpreter.py, src/music_discovery/agents/prompts/query.md, tests/unit/agents/test_llm_query_interpreter.py, tests/unit/agents/
- **Do:**
  - The LLM reads first and the parser runs only on fallback. Today the parser runs first and a parser clarification skips the LLM entirely (`agent_a_query.py:101`).
  - Replace "every hard constraint must also be found by the parser" with: the model's `cue` and value must appear verbatim in the query text. Soft wording still can't become hard, but the LLM is no longer limited to what the parser finds.
  - Keep values outside the lexicon instead of dropping them when their `source_span` appears verbatim in the query, and note them in `uncertainties`.
  - Add `semantic_prompts` (at most `MAX_SEMANTIC_PROMPTS`) to the draft, so the LLM writes the CLAP search text. Prompts describe sound only and may not name an artist or track absent from the query. Make sure `with_prompts` doesn't overwrite them.
  - Move the clarification decision to the LLM. Contradictions in the validated spec still produce a clarification, and a track ID not from the session still rejects the answer.
  - Publish prompt `query-v2`, with examples never taken from the test split.
  - Parser-built prompt expansions (cycle C5, P10.T11) stay in use on the fallback path only.
- **Done when:**
  - Table tests with `FakeStructuredLLM` cover: paraphrase accepted; out-of-lexicon value kept; invented cue rejected; invented track ID rejected; invalid output, timeout and rate limit each fall back to the parser with the reason recorded. Multi-turn hard-constraint preservation still passes.
- **Status:** [ ]

### P11.T06 — LLM candidate selector
- **Skills:** agent-orchestration, openrouter-llm, grounded-explanations
- **Depends on:** P11.T03
- **Files:** src/music_discovery/agents/llm_candidate_selector.py, src/music_discovery/agents/prompts/selection.md, config/retrieval.yaml, tests/unit/agents/test_llm_candidate_selector.py
- **Do:**
  - Input is the query, the validated spec and the shortlist. Each candidate is sent as an opaque alias (`c1`, `c2`, …) with title, artist, album, genres, capped tags and year, the fields the owner approved in ADR-0007. Missing values are sent as `null`.
  - Never send track IDs, URLs, licenses, raw scores, or user or session identifiers.
  - Output is an ordered list of aliases only. Reject the whole answer on an unknown alias or a duplicate. An empty list falls back to engine order. A shorter list is honest and is returned as is, with no padding.
  - Catalog text is untrusted input: the prompt says so, and alias validation limits what injected text can achieve.
  - `selection.shortlist_size` (default 30) lives in config. If `limit` exceeds it, skip selection and report `limit_exceeds_shortlist`.
- **Done when:**
  - Tests assert the exact outgoing payload has no track IDs or identifiers, and cover invented aliases, duplicates, empty and short answers, a malicious title, and each failure code falling back with a reason.
- **Status:** [ ]

### P11.T07 — Wire selection into Agent B and the orchestrator
- **Skills:** agent-orchestration, hybrid-retrieval, grounded-explanations
- **Depends on:** P11.T05, P11.T06
- **Files:** src/music_discovery/agents/agent_b_discovery.py, src/music_discovery/agents/orchestrator.py, src/music_discovery/domain/schemas.py, src/music_discovery/api/dependencies.py, tests/unit/agents/, tests/integration/
- **Do:**
  - `DiscoveryAgent.discover` fetches the shortlist from the unchanged retriever, applies the selector, and assigns ranks 1..n in the LLM's order.
  - Keep each `ScoreBreakdown` exactly as the engine computed it. Scores now explain evidence and need not fall in rank order, so check every consumer (match bands, descriptions, evidence) that assumes they do.
  - Add `ranking: "llm" | "engine"`, the model, the prompt version and the fallback reason to `RetrievalTrace`.
  - Clarification and `NO_CONFIDENT_MATCH` make no selection call.
  - Share `LLM_SEARCH_BUDGET_S` across both calls: the selection call passes what is left as `timeout_s`, and skips selection with a labelled reason when nothing is left.
  - Selection receives the updated spec on refinement, so feedback still changes the next results.
- **Done when:**
  - Property tests: a returned track is always in the shortlist, never violates a hard constraint and is never in `excluded_track_ids`. A test proves `retrieval/` has no LLM dependency. An integration test with the LLM failing still returns engine results, labelled. Boundary checks pass.
- **Status:** [ ]

### P11.T08 — API contract: show which path ran
- **Skills:** api-contracts, ux-states-and-evidence
- **Depends on:** P11.T07
- **Files:** src/music_discovery/api/schemas.py, src/music_discovery/api/mapping.py, src/music_discovery/application/capabilities.py, src/music_discovery/application/search_service.py, src/music_discovery/api/examples.py, tests/api/test_search.py, docs/api-changelog.md
- **Do:**
  - Additive only: `ranking_source: "llm" | "engine"`, `ranking_model: string | null`, and a `llm_selection` capability next to `llm_interpreter` (used, fallback, disabled).
  - `/api/health` reports the circuit state for both LLM tasks.
- **Done when:**
  - API tests cover LLM, fallback and disabled states. Fixtures are regenerated, with a changelog entry.
- **Status:** [ ]

### P11.T09 — Frontend data layer for ranking source
- **Skills:** api-contracts, ui-isolated-development
- **Depends on:** P11.T08
- **Files:** frontend/src/api/generated.ts, frontend/src/api/types.ts, frontend/src/mocks/fixtures/, frontend/src/hooks/README.md
- **Do:**
  - Regenerate types and fixtures, and add a mock scenario for LLM fallback.
  - **Flag for the UI track:** two things need a U-phase contract task. The interpreted-query area must say whether AI or the fallback produced the results, and the loading state must suit a search that can take up to `LLM_SEARCH_BUDGET_S`. Scores may no longer fall in rank order, so check how match strength reads in a result list.
- **Done when:**
  - `npm run contract:check` passes, and the fixtures carry the new fields.
- **Status:** [ ]

### P11.T10 — Evaluate LLM-first search on the dev split
- **Skills:** retrieval-evaluation, openrouter-llm
- **Depends on:** P11.T07
- **Files:** scripts/evaluate.py, src/music_discovery/evaluation/, artifacts/evaluation/{run_id}/*, docs/adr/0007-llm-first-search.md, docs/crisp-dm/iterations.md
- **Do:**
  - Add systems `llm_query_hybrid` (LLM parsing only) and `llm_full` (LLM parsing and selection), compared with `metadata_only`, `semantic_only` and `hybrid`.
  - Report P@5, R@5, nDCG@5, MRR, constraint satisfaction, diversity, latency, calls per search and fallback rate, and report the paraphrase set separately.
  - Dev split only; the test split stays untouched until P10. Runs use the response cache and may span several days at 50 requests/day.
  - The 20-track corpus makes the shortlist nearly the whole corpus, and there are only 8 judged dev queries: state that limit next to the numbers.
  - Log the run as a new cycle in `docs/crisp-dm/iterations.md` (ADR-0006): hypothesis, change, dev result, decision.
- **Done when:**
  - A second cached run gives identical metrics, the comparison table is in ADR-0007, and the cycle is recorded.
  - **Owner gate:** the owner reviews the table. If `llm_full` is worse than `hybrid`, the owner decides whether to continue, keep LLM parsing only, or revise. Nothing changes that default automatically.
- **Status:** [ ]

### P11.T11 — Turn it on by default
- **Skills:** openrouter-llm, implementation-roadmap, music-discovery-architecture
- **Depends on:** P11.T08, P11.T09, P11.T10
- **Files:** .env.example, config/llm.yaml, README.md, tests/integration/infrastructure/test_llm_live.py, skills/phases/functional/P10-final-evaluation-and-docs.md, docs/crisp-dm/business-understanding.md
- **Do:**
  - Add to the owner's open decisions in `business-understanding.md`: re-set T12 (p95 ≤ 2 s can't include two LLM calls) and decide which system T1–T4 name, all before the P10.T01 freeze. Draft only; the owner confirms.
  - Set `default_enabled: true` and put the provider and chosen chains in `.env.example`. A missing key still means a working, labelled deterministic system.
  - Add a live smoke test (`@pytest.mark.live`) for one full search with both LLM calls.
  - Rewrite P10.T02 so the LLM system is the primary system under test, not an optional ablation, with deterministic baselines kept for comparison.
- **Done when:**
  - The live test passes with the real key. With the key removed, a search still returns labelled engine results. Full default suite, boundary check and `contract:check` pass.
- **Status:** [ ]

## Exit criteria
- [ ] With a configured key, a normal search uses the LLM for parsing and for choosing results, and the response says so.
- [ ] With the LLM unavailable, search still works and reports the fallback.
- [ ] No returned track is outside the shortlist, violates a hard constraint, or is invented.
- [ ] No catalog dump, secret, or user or session identifier reaches the LLM (payload tests).
- [ ] Dev comparison against the deterministic system is recorded and reviewed by the owner.
