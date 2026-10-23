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
- **Notes:** `EvidenceBuilder(bands).build(candidate, track, matched_fields=, semantic=SemanticSignal, degraded=)` takes plain values (descriptions may import only `domain`); the orchestrator maps `HybridResult` into it. `DescriptionService.claims()` turns evidence into claims (one fixed sentence + chip + evidence reference each); `describe()` shows the strongest positive claim plus the top caveat (unverified constraint, no audio), every sentence validated, `None` without evidence. Validator: cited claims, ≤ 2 sentences, forbidden words, no numbers/percentages the claims do not state, instrument nouns and sound descriptors only inside quotes copied from a cited claim. Only expansion prompts are quoted: the request text can carry negations ("… without vocals") that CLAP does not understand, so a match on it reads "a strong match for your request" (added `SemanticEvidence.query_kind`, optional). τ chosen on dev (8 judged queries, 147 pairs): `tau_strong` 0.8, `tau_partial` 0.6; see `docs/calibration.md`. Test split not used.
- **Status:** [x]

### P06.T06 — Optional LLM description phrasing
- **Skills:** grounded-explanations, openrouter-llm
- **Depends on:** P06.T05, P06.T03
- **Files:** src/music_discovery/descriptions/llm_phrasing.py, tests/unit/descriptions/test_llm_phrasing.py
- **Do:**
  - LLM receives only the claim list; must cite claim ids per sentence; validator post-check; fallback to template; disabled by default.
- **Done when:**
  - Fake-LLM tests: cited output accepted; uncited/hallucinated/percentage output rejected ⇒ template used, reason logged.
- **Notes:** `LLMPhrasing(llm, config)` with prompt `descriptions/prompts/descriptions.md` (`descriptions-v1`); the LLM gets only `[{id, claim}]` JSON. Accepted only if the claim validator passes and the text still cites the caveat the template shows (an unverified constraint is never dropped). `DescriptionService(config, phrasing=None)`; new setting `LLM_DESCRIPTIONS=false` for the composition root (P08) to opt in. Rejections are logged with the reason and keep the template.
- **Status:** [x]

### P06.T07 — Session & feedback persistence
- **Skills:** agent-orchestration, domain-modeling
- **Depends on:** P01.T07, P01.T04
- **Files:** src/music_discovery/infrastructure/repositories.py (session/feedback), tests/integration/infrastructure/test_session_repository.py
- **Do:**
  - SQL tables for sessions, turns (query id, spec snapshot, result ids), feedback events; optimistic versioning on session updates.
- **Done when:**
  - Contract tests against fake + SQL; concurrent update with stale version raises.
- **Notes:** `SqlSessionRepository` / `SqlFeedbackRepository` over new tables `search_sessions` (version, feedback history JSON), `search_turns` (position, query id, spec snapshot, result ids, change summary; unique query id per session) and `feedback_events`. `save` is a compare-and-set (`UPDATE … WHERE version = expected`, insert refuses an existing id) inside one transaction, so a stale writer changes nothing. The tables are additive, so `SCHEMA_VERSION` stays 2 and an existing local database keeps working (`create_all` adds them). One contract suite runs against the fakes and SQLite.
- **Status:** [x]

### P06.T08 — Agent C feedback rules
- **Skills:** agent-orchestration
- **Depends on:** P06.T02, P06.T07
- **Files:** src/music_discovery/agents/feedback_rules.py, src/music_discovery/agents/agent_c_feedback.py, tests/unit/agents/test_feedback_rules.py, tests/unit/agents/test_feedback_properties.py
- **Do:**
  - Rule table for all 7 event types; change notes; validation (session/query/track membership, SELECT_TRACK map exception); `explain()` delegating to DescriptionService.
- **Done when:**
  - Unit test per rule; Hypothesis property tests: original query unchanged, hard constraints never dropped, idempotent set updates; base §8 example ("more electronic, less acoustic") preserves flute + chill.
- **Notes:** `feedback_rules.py`: pure `(spec, event, ctx) -> RuleResult(spec, note, rejected)` per event type, δ = 0.2; prompts rebuilt after every change. An attribute is a lexicon term or `attribute=<category>, value=<term>`. A change that would contradict a hard constraint (more vocals after "without vocals", more drums after "no drums") is rejected with a reason, never applied; unknown attributes are rejected. WRONG_INSTRUMENT excludes the track and adds a session note, keeping the instrument preference. `FeedbackAgent(lexicon, tracks, evidence, descriptions)`: `apply_feedback` raises SessionNotFound / QueryNotInSession / TrackNotInResults / TrackNotFound; a repeat (no change) gives `NextAction.NONE`. `explain(result: HybridResult)` returns candidates with evidence attached plus their explanation (instead of the skill's `explain(candidates, spec)`, which lacks the trace/matches the evidence needs). Hypothesis: original query, hard constraints and hard vocal choices survive any event sequence; track-set rules idempotent; version grows by one per change.
- **Status:** [x]

### P06.T09 — Free-text feedback normalization
- **Skills:** agent-orchestration, openrouter-llm
- **Depends on:** P06.T08
- **Files:** src/music_discovery/agents/feedback_text.py, tests/unit/agents/test_feedback_text.py
- **Do:**
  - Lexicon mapping "more X / less X / not X / no X" → typed events; optional LLM path with validation + fallback; unmappable ⇒ rejected with reason.
- **Done when:**
  - Tests for compound feedback ("more electronic, less acoustic" ⇒ two events) and unmappable text.
- **Notes:** `FeedbackTextNormalizer(lexicon, llm=None).normalize(text, session_id=, query_id=, event_id=, timestamp=)` -> `FeedbackText(accepted, events, reason, interpreter, llm_fallback_reason)`; events get ids `{event_id}.n` and keep the text in `free_text`. Lexicon path: clauses split at punctuation / and / but; a less-cue in the clause (less, fewer, not, no, without, too …) makes every term in it LESS_OF, otherwise MORE_OF (comparatives such as "darker" map through the lexicon). Feedback negation is always soft. LLM path: prompt `agents/prompts/feedback.md` (`feedback-v1`), every attribute must resolve through the lexicon or the answer is dropped for the lexicon reading. Also fixed in the rules: "more instrumental" means fewer vocals (it was read as more vocals).
- **Status:** [x]

### P06.T10 — Orchestrator & end-to-end flow (M4 acceptance)
- **Skills:** agent-orchestration
- **Depends on:** P06.T04, P06.T05, P06.T08
- **Files:** src/music_discovery/agents/orchestrator.py, tests/integration/agents/test_orchestrator.py
- **Do:**
  - `search()` and `refine()` flows: A → B → C.explain; session turn recording; "what changed" summary; degraded/clarification/no-match outcomes.
- **Done when:**
  - Integration test on the small local index: NL query ⇒ plate with descriptions; feedback ⇒ next plate changes in the expected direction (e.g. NOT_RELEVANT track gone, MORE_LIKE_THIS neighbors rise); multi-turn constraint preservation across 3 turns.
- **Notes:** `Orchestrator(query, discovery, feedback, sessions, feedback_events, clock, ids, feedback_text=None)` with `search()`, `refine()` and `refine_text()` (free text → events applied in order → one new search); each returns a `SearchTurn` (session, spec, query id, outcome with evidence on candidates, explanations, trace, change summary, feedback decision, LLM fallback reason). Rejected feedback and SELECT_TRACK record the event without a new search. Sessions are saved at the version they were read (stale writes raise); feedback events are stored after the session save. `FeedbackAgent.apply_feedback` gained an optional `spec` so a batch builds on earlier events. The integration test uses a 12-track catalog with the real BM25 and NumPy cosine indexes and the fake encoder (CLAP is `slow`); the real 20-track index is exercised in P06.T11.
- **Status:** [x]

### P06.T11 — Agent A & C component evaluation
- **Skills:** retrieval-evaluation, agent-orchestration
- **Depends on:** P06.T10, P05.T05
- **Files:** src/music_discovery/evaluation/agent_eval.py, data/evaluation/feedback_cases.jsonl, tests/unit/evaluation/test_agent_eval.py
- **Do:**
  - Agent A: per-category P/R/F1, hard-constraint accuracy, validity rate (LLM path when enabled). Agent C: spec-delta correctness, constraint preservation, ranking direction on `feedback_cases.jsonl`. Switch `evaluate.py` from manual specs to deterministic Agent A specs.
- **Done when:**
  - `evaluate.py --components agent_a,agent_c --split dev` writes `agent_a.csv` / `agent_c.csv` and metrics.
- **Notes:** `evaluation/agent_eval.py` + 10 cases in `data/evaluation/feedback_cases.jsonl` (7 dev, 3 test; track references are `rank:N` in the initial plate). `evaluate.py` now uses Agent A deterministic specs by default (`--specs manual` keeps the hand-written ones) and `--components agent_a,agent_c` writes `agent_a.csv`, `agent_c.csv` and a `components` block in `metrics.json` / `report.md`. Dev run 2026-10-23 (`p06-agents-dev`): Agent A micro F1 1.000, hard-constraint and vocals accuracy 1.000, validity 1.000 (not independent: the lexicon was written against these labels, the report says so); Agent C 8/8 cases, preservation 1.000, ranking direction 4/4. Finding: with Agent A specs hybrid dev nDCG@5 is 0.741 vs 0.787 with manual specs, semantic-only 0.720 vs 0.757. The only difference is the deterministic CLAP prompt expansions (manual specs have none); they hurt q01 and q16 most. Not changed here: tuning expansion weight / count is a retrieval calibration (dev only) for a follow-up task.
- **Status:** [x]

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
- **Notes:** Shortlist of 5 free models with structured-output support taken from the live `GET /models` listing (2026-10-23, 17 of 468 models free); free-tier limits recorded from the OpenRouter docs (20 req/min; 50/day under 10 credits, 1,000/day otherwise). `config/llm.yaml` holds the candidates and per-task chains (Gemma 4 31B primary); `scripts/llm_model_check.py` passes (all listed, free, json_schema). ADR-0004 proposes keeping LLM paths **disabled by default**: the deterministic parser already scores 1.000 on the dev labels, so no model can beat it there. Blocked on: (1) owner acceptance of ADR-0004; (2) the per-model Agent A comparison (`llm_model_check.py --evaluate`), which needs `OPENROUTER_API_KEY` (none on this machine); (3) data policies, which were not machine-readable and must be checked by the owner in the OpenRouter UI.
- **Status:** [!]

## Exit criteria (Milestone 4)
- [x] NL request ⇒ ranked plate with grounded descriptions; feedback changes the next plate predictably (P06.T10).
- [ ] All agent outputs schema-validated; LLM paths (OpenRouter free models) optional, with tested fallback and the chosen models recorded in ADR-0004.
- [x] Constraint preservation property tests green.
