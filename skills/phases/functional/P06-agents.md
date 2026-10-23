# P06 — Agents A/B/C, Grounded Descriptions, Sessions & Orchestrator

**Goal:** a natural-language request produces a ranked, explained plate; feedback updates the session state predictably while preserving constraints (Milestone 4). Agents coordinate deterministic services; LLMs are optional and always validated with deterministic fallback.
**LLM source:** OpenRouter free models — https://openrouter.ai/collections/free-models (see the `openrouter-llm` skill). Model IDs live in config, never in code.
**base.md:** §5.3, §6, §7 (Agent B), §8, §16.
**Depends on:** P04, P05.T03

### P06.T01 — Lexicon & deterministic query parser
- **Skills:** agent-orchestration
- **Depends on:** P01.T03
- **Files:** src/music_discovery/agents/lexicon/{mood,instrument,genre,tempo,energy,vocals,era,texture,cues}.yaml, src/music_discovery/agents/lexicon_loader.py, src/music_discovery/agents/query_parser.py, tests/unit/agents/test_query_parser.py
- **Do:**
  - Versioned lexicon (canonical term → synonyms), cue lists (negation, hard, intensifiers); phrase spotting, weights, negation scope, hard-vs-soft classification, unmapped musical words → `uncertainties`.
  - Wire the lexicon into MetadataRetriever synonym expansion (replace the P04.T01 stub).
- **Done when:**
  - Table tests: "Something chill with a flute" ⇒ 2 soft prefs, 0 hard; "Calm acoustic music without vocals" ⇒ vocals excluded hard; "slightly dark" weight < "very dark"; negation scope correct.
- **Notes:** Lexicon is 9 YAML files (261 phrases; each phrase maps to exactly one canonical term, checked at load; version = content hash, `QueryParser.lexicon_version`). Canonical terms are near-exact synonyms (laid-back -> relaxed, chill stays separate) so parser output lines up with `expected_attributes`: all 20 evaluation queries match their labels and hard constraints (table test). Hard/soft rules: "without"/"no" + vocals or instrument -> hard; "without" + genre -> negative soft preference (q15 label), "no" + genre or "at all" -> hard; numeric ranges (duration, era years/decades, bpm) -> hard; "only"/"strictly"/"must" -> required (mood/energy/texture/tempo stay soft, with an uncertainty). Hard instrument/genre exclusions also add a negative preference, since the instrument constraint is always UNKNOWN in the MVP. Vocal type (female/male/rapping) is an uncertainty, contradictions ask a clarification question and drop the conflicting parts. Expansion is wired in `scripts/_runtime.py`; it drops synonyms whose words contain a shorter expansion ("chill out" next to "chill"), which otherwise double-counted FMA's "Chill-out" genre and lowered q01. Dev run (manual specs, weights unchanged): hybrid nDCG@5 0.780 -> 0.787, P@5 0.525 -> 0.550, metadata-only nDCG@5 0.412 -> 0.436; test split not run.
- **Status:** [x]

### P06.T02 — Agent A (query understanding)
- **Skills:** agent-orchestration, domain-modeling
- **Depends on:** P06.T01, P03.T06
- **Files:** src/music_discovery/agents/agent_a_query.py, tests/unit/agents/test_agent_a.py
- **Do:**
  - `QueryAgent.interpret(query, state)`: parser → spec; semantic prompts via prompt builder; session context (previous spec) carried for follow-up queries; clarification only when not actionable or contradictory; never invents catalog entries; never calls retrieval/CLAP/Discogs.
- **Done when:**
  - All 20 evaluation queries yield valid specs; clarification cases tested; outputs validated by Pydantic in every path.
- **Notes:** `QueryAgent(lexicon).interpret(query, session)`. Follow-up = the query opens with a `follow_up` cue (new list in `cues.yaml`, loader field `Cues.follow_up`) or answers a pending clarification; anything else is a new search. A refinement appends the follow-up text to `original_query` as a new sentence (owner decision: CLAP and lexical matching see both; a rejected follow-up leaves it unchanged; `SearchSession.original_query` stays the first turn's text) and keeps the feedback-set track ids and diversity, and every hard constraint; new wording overrides earlier soft preferences, a newly stated range replaces the earlier one, and soft vocal wording never weakens an earlier hard choice. A follow-up contradicting an earlier hard constraint returns the previous spec with a clarification question. LLM path is left to P06.T03.
- **Status:** [x]

### P06.T03 — OpenRouter LLM adapter & LLM query interpreter
- **Skills:** agent-orchestration, openrouter-llm
- **Depends on:** P06.T02, P00.T02
- **Files:** src/music_discovery/infrastructure/llm.py, src/music_discovery/agents/llm_query_interpreter.py, tests/unit/agents/test_llm_query_interpreter.py
- **Do:**
  - `StructuredLLM` implementation for **OpenRouter** (OpenAI-compatible `base_url`, `:free` models from `LLM_MODEL` + `LLM_FALLBACK_MODELS`); structured-output strategy picked from each model's `supported_parameters` (json_schema → tool call → prompt-only JSON, always Pydantic-validated); 429/quota/model-gone handling; circuit breaker; response cache for evaluation; no keys in logs. Until P06.T12 picks a model, use any current free model with tool or structured-output support. Interpreter prompt per the skill; draft → lexicon normalization → validation → fallback to deterministic on any failure; `spec.interpreter` recorded. Feature flag `LLM_PROVIDER` empty ⇒ disabled.
- **Done when:**
  - Adapter tests with `httpx.MockTransport`: each output strategy, 429 + `Retry-After`, model not found → next fallback model, timeout, circuit breaker.
  - Fake-LLM tests: valid output accepted; invalid JSON, schema violation, hallucinated track ids, soft→hard escalation all rejected ⇒ deterministic fallback with reason.
  - System works end-to-end with the LLM disabled.
- **Notes:** `infrastructure/llm.py` (`OpenRouterLLM`, `build_llm(settings)`; plain httpx, injectable transport/sleep/clock) and `agents/llm_query_interpreter.py` with the versioned prompt `agents/prompts/query.md` (`query-v1`, lexicon vocabulary injected). Added settings `LLM_MODEL_QUERY/FEEDBACK/DESCRIPTIONS`. The LLM draft is accepted only if every hard choice it makes is also in the deterministic parse (hard constraints and clarification always come from the parser); values are mapped to lexicon terms or dropped with a note; reference ids not in the session are rejected. `QueryAgent(lexicon, llm=None)`; `interpret_traced()` exposes the fallback reason. No API key on this machine: the `live` smoke test (`tests/integration/infrastructure/test_llm_live.py`) has not been run; `.env.example` keeps `LLM_MODEL` empty until P06.T12.
- **Status:** [x]

### P06.T04 — Agent B (discovery orchestration)
- **Skills:** agent-orchestration, hybrid-retrieval
- **Depends on:** P06.T02, P04.T07
- **Files:** src/music_discovery/agents/agent_b_discovery.py, tests/unit/agents/test_agent_b.py
- **Do:**
  - `DiscoveryAgent.discover(spec, limit)` → hybrid retriever; propagates degraded flags and NO_CONFIDENT_MATCH; dedup/diversity via retriever; no descriptions, no LLM scoring.
- **Done when:**
  - Tests with fake retriever: limit honored, degraded propagated, no-confident-match propagated, deterministic output.
- **Notes:** `DiscoveryAgent(retriever, corpus=None).discover(spec, limit) -> HybridResult` (the retriever's own result type: outcome + trace + matched fields + semantic hits, which the evidence builder needs). Also: a spec that needs clarification returns NEEDS_CLARIFICATION without retrieving; a spec without semantic prompts gets the deterministic ones; `limit` must be 1..100.
- **Status:** [x]

### P06.T05 — Evidence builder, claim validator & template descriptions
- **Skills:** grounded-explanations
- **Depends on:** P04.T07, P01.T04
- **Files:** src/music_discovery/descriptions/evidence_builder.py, src/music_discovery/descriptions/claim_validator.py, src/music_discovery/descriptions/description_service.py, config/descriptions.yaml, tests/unit/descriptions/*.py
- **Do:**
  - Build `TrackEvidence` from candidate + trace + catalog; strength bands; template generator for `description` + `match_reasons`; validator with forbidden lexicon and claim coverage; conservative/None output when evidence is thin.
  - τ (strength-band threshold) is config, not calibrated in P05: choose it from dev-split queries only, never test, and record the choice in `docs/calibration.md`.
- **Done when:**
  - Golden tests; forbidden phrasing rejected; no-audio track never gets sound descriptors; every template sentence maps to an evidence item.
- **Status:** [ ]

### P06.T06 — Optional LLM description phrasing
- **Skills:** grounded-explanations, openrouter-llm
- **Depends on:** P06.T05, P06.T03
- **Files:** src/music_discovery/descriptions/llm_phrasing.py, tests/unit/descriptions/test_llm_phrasing.py
- **Do:**
  - LLM receives only the claim list; must cite claim ids per sentence; validator post-check; fallback to template; disabled by default.
- **Done when:**
  - Fake-LLM tests: cited output accepted; uncited/hallucinated/percentage output rejected ⇒ template used, reason logged.
- **Status:** [ ]

### P06.T07 — Session & feedback persistence
- **Skills:** agent-orchestration, domain-modeling
- **Depends on:** P01.T07, P01.T04
- **Files:** src/music_discovery/infrastructure/repositories.py (session/feedback), tests/integration/infrastructure/test_session_repository.py
- **Do:**
  - SQL tables for sessions, turns (query id, spec snapshot, result ids), feedback events; optimistic versioning on session updates.
- **Done when:**
  - Contract tests against fake + SQL; concurrent update with stale version raises.
- **Status:** [ ]

### P06.T08 — Agent C feedback rules
- **Skills:** agent-orchestration
- **Depends on:** P06.T02, P06.T07
- **Files:** src/music_discovery/agents/feedback_rules.py, src/music_discovery/agents/agent_c_feedback.py, tests/unit/agents/test_feedback_rules.py, tests/unit/agents/test_feedback_properties.py
- **Do:**
  - Rule table for all 7 event types; change notes; validation (session/query/track membership, SELECT_TRACK map exception); `explain()` delegating to DescriptionService.
- **Done when:**
  - Unit test per rule; Hypothesis property tests: original query unchanged, hard constraints never dropped, idempotent set updates; base §8 example ("more electronic, less acoustic") preserves flute + chill.
- **Status:** [ ]

### P06.T09 — Free-text feedback normalization
- **Skills:** agent-orchestration, openrouter-llm
- **Depends on:** P06.T08
- **Files:** src/music_discovery/agents/feedback_text.py, tests/unit/agents/test_feedback_text.py
- **Do:**
  - Lexicon mapping "more X / less X / not X / no X" → typed events; optional LLM path with validation + fallback; unmappable ⇒ rejected with reason.
- **Done when:**
  - Tests for compound feedback ("more electronic, less acoustic" ⇒ two events) and unmappable text.
- **Status:** [ ]

### P06.T10 — Orchestrator & end-to-end flow (M4 acceptance)
- **Skills:** agent-orchestration
- **Depends on:** P06.T04, P06.T05, P06.T08
- **Files:** src/music_discovery/agents/orchestrator.py, tests/integration/agents/test_orchestrator.py
- **Do:**
  - `search()` and `refine()` flows: A → B → C.explain; session turn recording; "what changed" summary; degraded/clarification/no-match outcomes.
- **Done when:**
  - Integration test on the small local index: NL query ⇒ plate with descriptions; feedback ⇒ next plate changes in the expected direction (e.g. NOT_RELEVANT track gone, MORE_LIKE_THIS neighbors rise); multi-turn constraint preservation across 3 turns.
- **Status:** [ ]

### P06.T11 — Agent A & C component evaluation
- **Skills:** retrieval-evaluation, agent-orchestration
- **Depends on:** P06.T10, P05.T05
- **Files:** src/music_discovery/evaluation/agent_eval.py, data/evaluation/feedback_cases.jsonl, tests/unit/evaluation/test_agent_eval.py
- **Do:**
  - Agent A: per-category P/R/F1, hard-constraint accuracy, validity rate (LLM path when enabled). Agent C: spec-delta correctness, constraint preservation, ranking direction on `feedback_cases.jsonl`. Switch `evaluate.py` from manual specs to deterministic Agent A specs.
- **Done when:**
  - `evaluate.py --components agent_a,agent_c --split dev` writes `agent_a.csv` / `agent_c.csv` and metrics.
- **Status:** [ ]

### P06.T12 — Free-model selection (ADR)
- **Skills:** openrouter-llm, retrieval-evaluation
- **Depends on:** P06.T03, P06.T11
- **Files:** docs/adr/0004-llm-models.md, scripts/llm_model_check.py, config/llm.yaml
- **Do:**
  - Shortlist 3–5 current `:free` models from https://openrouter.ai/collections/free-models that support tool calling or structured outputs. Record their IDs, context length, data policy (e.g. whether the provider trains on free-tier inputs) and the free-tier rate/daily limits from the OpenRouter docs, with the date.
  - Run the Agent A dev queries through each one (cached): structured-output validity, attribute F1, hard-constraint accuracy, p50/p95 latency, compared against the deterministic parser.
  - Choose a primary model and fallbacks per task (query / feedback / descriptions), or keep LLM paths disabled if no free model beats the deterministic baseline.
  - `llm_model_check.py`: checks via `GET /api/v1/models` that the configured models still exist and are still free, and warns if not.
- **Done when:**
  - ADR accepted by the user; `config/llm.yaml` / `.env.example` updated; the model check passes.
- **Status:** [ ]

## Exit criteria (Milestone 4)
- [ ] NL request ⇒ ranked plate with grounded descriptions; feedback changes the next plate predictably (P06.T10).
- [ ] All agent outputs schema-validated; LLM paths (OpenRouter free models) optional, with tested fallback and the chosen models recorded in ADR-0004.
- [ ] Constraint preservation property tests green.
