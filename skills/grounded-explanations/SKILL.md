---
name: grounded-explanations
description: Evidence-grounded track descriptions and match reasons — building TrackEvidence from retrieval traces and catalog facts, the allowed-claim vocabulary, template generation, optional LLM phrasing constrained by a claim validator, and factuality checks. Load for descriptions/evidence_builder.py, descriptions/description_service.py, any text shown to users about why a track matched, or when auditing generated descriptions.
---

# Grounded Explanations

Spec: `base.md` §8 (explanation generation), §9.4, §16, §20 ("no unsupported track claims").

## 1. Evidence first

`descriptions/evidence_builder.py` builds `TrackEvidence` from the `RankedCandidate` + trace + catalog record:

```python
class TrackEvidence(BaseModel):
    track_id: str
    metadata_matches: list[FieldMatch]          # field, term, source, kind=lexical|tag
    genre_matches: list[TagMatch]                # tag, source (discogs|fma)
    style_matches: list[TagMatch]
    semantic: SemanticEvidence | None            # prompt, raw_cosine, normalized, rank, model_id, strength band
    retrieval_sources: list[str]
    known_audio_features: list[AudioFeature]     # name, value, unit, source, estimated: bool
    human_labels: list[HumanLabel]               # only from evaluation judgments, if exposed at all
    constraint_results: list[ConstraintResult]
    uncertainty_flags: list[str]                 # no_audio, semantic_unavailable, constraint_unknown:vocals, …
```

Strength bands for semantic evidence are derived from the **rank and normalized score within the query** (e.g. `strong` = top-3 and normalized ≥ τ), with τ in config. Never expose raw cosine as a percentage.

## 2. Allowed claims

Every sentence in a description must map to ≥ 1 evidence item. Claim types and safe phrasings:

| Evidence | Allowed phrasing | Forbidden |
|---|---|---|
| genre/style tag | "Tagged as ambient on Discogs." / "Listed under Folk in FMA." | "This is an ambient track" as audible fact without tag source |
| semantic (strong) | "Its audio is a strong match for 'chill music with a flute'." | "Features a flute", "contains flute", "87 % flute" |
| semantic (moderate) | "Its audio is a partial match for the requested sound." | probability language |
| audio feature (estimated) | "Estimated tempo around 90 BPM." | "Slow and relaxing" unless mood is separately evidenced |
| metadata match | "Title mentions 'flute'." | inferring instrumentation from a title |
| relationship | "Same label as <track you liked>." | "Sounds like …" |
| constraint UNKNOWN | "Vocal content could not be verified." | silently implying compliance |
| no audio | "Audio analysis unavailable; matched on catalog metadata." | any sound description |

Instrument presence may be stated as fact **only** from human labels (evaluation data) — and the plan does not expose those in product search, so in practice: never.

## 3. Generation

`descriptions/description_service.py`:

1. **Template generator (default, deterministic):** picks 1–2 sentences from ranked evidence (semantic → tags → features → uncertainty). Produces `description` and `match_reasons: list[str]` (short chips like "Strong audio match", "Tagged: Ambient", "No audio analysis").
2. **Optional LLM phrasing** (OpenRouter free model via `StructuredLLM`, `task="descriptions"`; see `openrouter-llm`): the LLM receives only the *claim list* (not the catalog, not the web) and must return text + `claim_ids` per sentence via structured output. The validator rejects outputs with uncited sentences, forbidden lexicon (`contains`, `features`, `%`, `probability`, instrument nouns not present in a semantic-prompt claim), or > 2 sentences ⇒ fall back to template.
3. When evidence is too thin, return a conservative description ("Matched on catalog metadata only.") or `None` — never pad.

## 4. Validator (`descriptions/claim_validator.py`)

Pure function `validate(text, claims, evidence) -> ValidationResult(ok, violations)`. Used by the service, by tests, by the evaluation (P10 description factuality), and by the `evidence-auditor` agent.

## 5. Tests

- Golden tests: evidence fixture → exact template output.
- Forbidden-phrasing tests: "contains a flute" rejected when only semantic evidence exists; percentages rejected; no-audio track never gets sound adjectives.
- LLM path with fake LLM: valid cited output accepted; uncited/hallucinated output → template fallback, reason logged.
