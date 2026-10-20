---
name: agent-orchestration
description: Implementing the three logical agents and their orchestrator — Agent A (query → validated SearchSpecification, deterministic lexicon parser first, optional LLM structured output with fallback), Agent B (orchestrates hybrid retrieval, no LLM scoring), Agent C (feedback → spec update with constraint preservation, and explanations via descriptions/), plus the search session model. Load for anything in src/music_discovery/agents/, the lexicon, session state, feedback update rules, or LLM adapter wiring.
---

# Agent Orchestration

Spec: `base.md` §5.3, §6, §7, §8, §3 (rules). Agents are **thin coordinators with validated contracts**, not autonomous loops (base §19: no debate, no autonomous loops).

## 1. Shape

```python
class QueryAgent:        # Agent A — agents/agent_a_query.py
    def interpret(self, query: str, state: SearchSession | None) -> SearchSpecification: ...

class DiscoveryAgent:    # Agent B — agents/agent_b_discovery.py
    def discover(self, spec: SearchSpecification, limit: int) -> DiscoveryResult: ...   # ranked set + trace

class FeedbackAgent:     # Agent C — agents/agent_c_feedback.py
    def apply_feedback(self, session: SearchSession, event: FeedbackEvent) -> FeedbackDecision: ...
    def explain(self, candidates: Sequence[RankedCandidate], spec: SearchSpecification) -> list[Explanation]: ...

class Orchestrator:      # agents/orchestrator.py
    def search(self, query: str, session: SearchSession | None, limit: int) -> SearchTurn: ...
    def refine(self, session: SearchSession, event: FeedbackEvent, limit: int) -> SearchTurn: ...
```

Each agent receives collaborators via the constructor (retrieval services, description service, `StructuredLLM | None`, lexicon, clock, id generator). None of them imports infrastructure, Discogs, CLAP, or SQL.

## 2. Agent A — query understanding

**Deterministic parser first** (`agents/query_parser.py` + `agents/lexicon/*.yaml`). It is the fallback and the evaluation baseline for A.

Lexicon (versioned data, `lexicon_version`):

```yaml
mood:
  chill: [chill, chilled, laid-back, laid back, relaxed, mellow, calm, easygoing]
  dark: [dark, ominous, brooding, sinister]
instrument:
  flute: [flute, flutes, pan flute, woodwind]   # "woodwind" → flute at lower weight
  piano: [piano, keys, keyboard]
vocals:
  female_vocals: [female vocals, female singer, woman singing]
negation_cues: [without, no, not, minus, avoid]
hard_cues: [only, strictly, must, exclusively, no]   # "no X" = hard; "less X" = soft
intensifiers: {very: 1.2, really: 1.2, slightly: 0.6, a bit: 0.6, somewhat: 0.7}
```

Rules:
1. Normalize (casefold, unicode, hyphen variants); longest-match phrase spotting over the lexicon.
2. Weights: base by category (instrument named with "with a X" ≈ 1.0, mood ≈ 0.7), scaled by intensifiers, clipped to [0,1].
3. **Hard vs soft:** hard only with explicit cues — "instrumental only", "no vocals", "without drums", "before 1990". "Something chill with a flute" ⇒ two soft preferences, zero hard constraints (base §5.3).
4. Negation scope: cue applies to the next attribute phrase only.
5. Unknown words are kept in `original_query` (CLAP sees them) and listed in `uncertainties` when they look musical but unmapped.
6. Clarification only when nothing actionable is extracted **and** the query is not usable as a CLAP prompt (e.g. "something", "music please" → still actionable as broad; empty or contradictory → clarify). Contradictions ("no vocals with female vocals") ⇒ `needs_clarification=True` with a question; never guess.
7. Build `semantic_prompts` via the deterministic prompt builder (≤ 4).

**Optional LLM interpreter** (`agents/llm_query_interpreter.py`):
- Uses `domain.protocols.StructuredLLM.generate(task="query", schema=SearchSpecificationDraft, system=…, user=…)`; the concrete adapter is `infrastructure/llm.py`, backed by **OpenRouter free models** (https://openrouter.ai/collections/free-models). Load the `openrouter-llm` skill for the adapter, model config (`LLM_MODEL`, `LLM_FALLBACK_MODELS`), structured-output strategy and free-tier limits.
- The draft is validated → post-processed by the same lexicon normalizer (map synonyms to canonical terms, reject unknown categories) → constraint sanity check.
- Any exception, invalid output, rate limit, unavailable model, or timeout ⇒ deterministic parser; `spec.interpreter` records which ran and `spec.interpreter_model` records the OpenRouter model that answered. Agent A must never output tracks/artists not in the query (validator: `reference_track_ids` must come from session state, not the LLM).
- Prompt forbids: inventing catalog entries, claiming detection of instruments, turning soft wording into hard constraints.

## 3. Agent B — discovery

- Calls `HybridRetriever(mode="hybrid")` with the spec; returns ranked candidates + trace. If the semantic signal is unavailable, B proceeds and flags `degraded=["semantic_unavailable"]`.
- May request semantic prompts from A/prompt builder (base §7.3); it doesn't invent them itself.
- Does **not** generate descriptions (base §7 output) and does not use an LLM for scores.

## 4. Agent C — feedback

Deterministic update table (`agents/feedback_rules.py`), each rule a pure function `(spec, event, context) -> (spec', change_note)`:

| Event | Spec change | next_action |
|---|---|---|
| `MORE_LIKE_THIS` | add track to `reference_track_ids` | `REFINE_SEARCH` |
| `LESS_LIKE_THIS` | add to `negative_reference_track_ids` | `REFINE_SEARCH` |
| `NOT_RELEVANT` | add to `excluded_track_ids` | `REFINE_SEARCH` |
| `WRONG_INSTRUMENT` (attribute=instrument) | exclude the track; lower trust of semantic-only matches for that instrument in this session (`uncertainties` note); **do not** remove the instrument preference | `REFINE_SEARCH` |
| `MORE_OF_ATTRIBUTE` | raise weight (+δ, clip 1) or add preference in the attribute's category; remove from negatives | `REFINE_SEARCH` |
| `LESS_OF_ATTRIBUTE` | lower weight (−δ) or add to `negative_preferences` (soft) | `REFINE_SEARCH` |
| `SELECT_TRACK` | no spec change; record | `SHOW_DETAILS` |

Invariants (property-tested):
- `original_query` never changes; hard constraints are **never dropped** by feedback (there is no event that removes them).
- Applying the same event twice is idempotent for set-based fields.
- "More electronic, less acoustic" (two events, or free text normalized by the optional LLM into two events) keeps flute + chill preferences intact (base §8 example).
- Each turn appends `(spec_version, event, change_note)` to the session history; the API can show "what changed".

Free-text feedback: optional LLM (OpenRouter free model, `task="feedback"`) maps text → `list[FeedbackEvent]` (validated); fallback lexicon mapping ("more X" / "less X"); unmappable ⇒ `accepted=false` with reason.

Explanations: Agent C calls `descriptions.DescriptionService` (see `grounded-explanations`); it never writes free prose itself.

## 5. Session model

`SearchSession(session_id, created_at, turns: list[SearchTurnRecord], current_spec, spec_history, feedback_history, shown_track_ids_by_query)` persisted through `SessionRepository`. Feedback validation: session exists, `query_id` belongs to it, `track_id` was in that query's results (except `SELECT_TRACK` from the map, allowed for any catalog track — make this an explicit rule).

## 6. Tests

- A: the 20 evaluation queries + edge cases (negation, intensifiers, hard cues, contradictions, empty) as table tests; LLM path with a `FakeStructuredLLM` returning valid, invalid, and hallucinating outputs ⇒ fallback works and is recorded.
- B: orchestration with fake retrievers; degraded flag propagation.
- C: every rule; multi-turn constraint preservation (base §18 M4); ranking changes predictably after feedback on a fixture corpus.
- Orchestrator: end-to-end with fakes; with a real small index under `integration`.
