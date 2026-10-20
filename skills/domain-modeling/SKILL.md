---
name: domain-modeling
description: Conventions for the music discovery domain layer — Track/Artist/Release/TrackAudio entities, SearchSpecification, FeedbackEvent, TrackEvidence, ScoreBreakdown, Protocols and error types, with the "missing is not zero" rule. Load when adding or changing anything in src/music_discovery/domain/, defining a Pydantic schema, adding a Protocol, or deciding how to represent an optional/unknown value.
---

# Domain Modeling

Spec: `base.md` §5, §6 (SearchSpecification), §8 (FeedbackEvent, TrackEvidence), §13 (public DTOs).

## 1. Files

| File | Contents |
|---|---|
| `domain/models.py` | Entities: `Track`, `Artist`, `Label`, `Release`, `TrackAudio`, `TrackRelationship`, `ExternalId`, `CrossSourceMatch`, `SearchSession` |
| `domain/schemas.py` | Value/contract objects: `SearchSpecification`, `WeightedPreference`, `HardConstraint`, `FeedbackEvent`, `TrackEvidence`, `ScoreBreakdown`, `RankedCandidate`, `SearchOutcome` |
| `domain/errors.py` | Exception hierarchy (below) |
| `domain/protocols.py` | `TrackRepository`, `SessionRepository`, `FeedbackRepository`, `EmbeddingStore`, `VectorIndex`, `TextEncoder`, `AudioEncoder`, `StructuredLLM`, `SpatialRepository`, `Clock`, `IdGenerator` |

Public API DTOs are **not** domain schemas — they live in `api/` and are mapped from domain objects (see `api-contracts`). Domain schemas may evolve without breaking the wire format.

## 2. Modeling rules

1. **Pydantic v2, frozen by default.** `model_config = ConfigDict(frozen=True, extra="forbid")`. Mutation = `model_copy(update=...)`. Sessions are the only stateful aggregate and are versioned.
2. **Stable internal IDs** are opaque strings with a source prefix: `trk_…`, `art_…`, `rel_…`, `lbl_…`. Generate deterministically from the source key (e.g. `uuid5(NAMESPACE, "fma:track:2")`) so re-imports are idempotent. External IDs live in `ExternalId(source="discogs"|"fma", kind="release"|"master"|"artist"|"track", value="…")`.
3. **Missing ≠ zero ≠ false.** Optional facts are `T | None`. Tri-state facts use enums, never bools:
   ```python
   class Evidence(StrEnum): PRESENT = "present"; ABSENT = "absent"; UNKNOWN = "unknown"
   class ConstraintStatus(StrEnum): SATISFIED = "satisfied"; VIOLATED = "violated"; UNKNOWN = "unknown"
   class EvidenceStatus(StrEnum): AUDIO_AND_METADATA = "audio_and_metadata"; METADATA_ONLY = "metadata_only"; AUDIO_ONLY = "audio_only"
   ```
   `ScoreBreakdown.semantic: float | None` — `None` means "not computed", never "irrelevant".
4. **Provenance travels with facts.** Any value that came from a source or a model carries `source` (and `confidence` when inferred): genres from Discogs vs FMA, matches with `method` + `confidence`, embeddings with `model_id` + `embedding_version`.
5. **Validation lives in the schema.** Weights in `[0, 1]`, `diversity` in `[0, 1]`, non-empty `original_query`, no duplicate preference values, a value cannot be both preferred and negative, hard constraints must be well-formed. Contradictory hard constraints (e.g. `vocals=required` and `vocals=excluded`) raise `ContradictoryConstraintsError` at construction.
6. **No I/O, no heavy deps.** `domain` imports only stdlib, pydantic, and (for type hints) numpy.

## 3. SearchSpecification (target shape)

```python
class WeightedPreference(BaseModel):
    value: str               # normalized lexicon term, e.g. "chill", "flute"
    weight: float = Field(ge=0, le=1)
    source_span: str | None  # text that produced it, for explanations

class HardConstraint(BaseModel):
    attribute: Literal["vocals", "instrument", "genre", "era", "tempo", "duration"]
    operator: Literal["required", "excluded", "range"]
    value: str | None = None
    range: tuple[float | None, float | None] | None = None

class SearchSpecification(BaseModel):
    spec_version: int = 1
    original_query: str
    mood_preferences: list[WeightedPreference] = []
    instrument_preferences: list[WeightedPreference] = []
    genre_preferences: list[WeightedPreference] = []
    tempo_preferences: list[WeightedPreference] = []
    energy_preferences: list[WeightedPreference] = []
    texture_preferences: list[WeightedPreference] = []
    era_preferences: list[WeightedPreference] = []
    vocal_preferences: Literal["required", "preferred", "avoided", "excluded", "unspecified"] = "unspecified"
    hard_constraints: list[HardConstraint] = []
    negative_preferences: list[WeightedPreference] = []
    reference_track_ids: list[str] = []
    negative_reference_track_ids: list[str] = []
    excluded_track_ids: list[str] = []
    semantic_prompts: list[str] = []   # controlled expansions (≤ 4), never requirements
    diversity: float = 0.5
    needs_clarification: bool = False
    clarification_question: str | None = None
    uncertainties: list[str] = []
    interpreter: Literal["deterministic", "llm"] = "deterministic"
    interpreter_model: str | None = None   # OpenRouter model id that answered, when interpreter="llm"
```

`vocal_preferences="excluded"` must be mirrored by a `HardConstraint(attribute="vocals", operator="excluded")` only when the user said so explicitly ("instrumental only", "no vocals") — soft wording ("mostly instrumental") stays a preference.

## 4. Error hierarchy

```
MusicDiscoveryError
├── DataSourceError        (DiscogsRateLimited, DiscogsUnavailable, DiscogsResponseInvalid)
├── AudioError             (AudioMissing, AudioDecodeError)
├── EmbeddingError         (ModelLoadError, InvalidEmbedding, EmbeddingVersionMismatch, IndexEntryMissing)
├── AgentOutputError       (invalid structured output — triggers deterministic fallback)
├── ConstraintError        (ContradictoryConstraintsError, InvalidConstraintError)
├── SpatialArtifactError   (ProjectionMissing, ProjectionMismatch)
├── SessionError           (SessionNotFound, QueryNotInSession, TrackNotInResults)
└── NotFoundError          (TrackNotFound)
```

Each error has a stable machine `code` (snake_case) that `api/` maps to HTTP status — the API never inspects messages.

## 5. Protocols

Keep them minimal and synchronous unless a caller truly needs async. Example:

```python
class VectorIndex(Protocol):
    @property
    def model_id(self) -> str: ...
    def search(self, query: np.ndarray, k: int, *, restrict_to: Collection[str] | None = None) -> list[tuple[str, float]]: ...
    def get(self, track_id: str) -> np.ndarray | None: ...
    def __contains__(self, track_id: str) -> bool: ...
```

Every protocol gets an in-memory fake in `tests/fakes/` in the same task that introduces it.

## 6. Tests to write with any model change

- Round-trip JSON (`model_validate(model.model_dump(mode="json"))`).
- Rejection cases (weights out of range, contradictory constraints, unknown fields).
- `None` preserved through serialization (no default-to-zero).
