# P01 — Domain Model, Protocols & Persistence

**Goal:** validated domain types and service interfaces that every later layer builds on, plus a SQLite implementation of the repositories.
**base.md:** §5 (domain model), §6 output, §8 (FeedbackEvent, TrackEvidence), §16 (errors), §3 (rules).
**Depends on:** P00

### P01.T01 — Identifiers, enums & value types
- **Skills:** domain-modeling
- **Depends on:** P00
- **Files:** src/music_discovery/domain/ids.py, src/music_discovery/domain/enums.py, tests/unit/domain/test_ids.py
- **Do:**
  - Deterministic internal IDs (`trk_`, `art_`, `rel_`, `lbl_`, `ses_`, `qry_`, `evt_`) via uuid5 of a source key; `ExternalId(source, kind, value)`.
  - Enums: `Evidence`, `ConstraintStatus`, `EvidenceStatus`, `FeedbackType` (7 values, base §8), `NextAction`, `SearchOutcomeKind`, `Capability` status.
- **Done when:**
  - Same source key ⇒ same ID across runs; different sources never collide (property test).
- **Status:** [ ]

### P01.T02 — Catalog entities
- **Skills:** domain-modeling
- **Depends on:** P01.T01
- **Files:** src/music_discovery/domain/models.py, tests/unit/domain/test_models.py
- **Do:**
  - `Track` with every base §5.1 field (optional fields `None` by default), `ArtistReference`, `LabelReference`, `Artist`, `Label`, `Release` (with structured `track_listing`), `TrackAudio`, `TrackRelationship`, `CrossSourceMatch`, `Provenance` (source, imported_at, confidence?).
  - Derived property `evidence_status` (audio_and_metadata / metadata_only).
- **Done when:**
  - JSON round-trip tests; `None` preserved; frozen models reject mutation; extra fields rejected.
- **Status:** [ ]

### P01.T03 — SearchSpecification & constraints
- **Skills:** domain-modeling, agent-orchestration
- **Depends on:** P01.T01
- **Files:** src/music_discovery/domain/schemas.py, tests/unit/domain/test_search_specification.py
- **Do:**
  - `WeightedPreference`, `HardConstraint`, `SearchSpecification` per the skill (incl. `semantic_prompts`, reference/negative/excluded ids, `interpreter`, `spec_version`).
  - Validators: weight/diversity ranges, non-empty query, no value both preferred and negative, ≤ 4 semantic prompts, contradictory hard constraints ⇒ `ContradictoryConstraintsError`.
- **Done when:**
  - The base §5.3 example JSON validates unchanged (modulo added defaults).
  - Rejection tests for each validator.
- **Status:** [ ]

### P01.T04 — Feedback, evidence, ranking & session schemas
- **Skills:** domain-modeling, grounded-explanations
- **Depends on:** P01.T02, P01.T03
- **Files:** src/music_discovery/domain/schemas.py, src/music_discovery/domain/models.py (SearchSession), tests/unit/domain/test_feedback_and_evidence.py
- **Do:**
  - `FeedbackEvent` (base §8 fields + optional `free_text`), `TrackEvidence` and its parts, `ScoreBreakdown` (all signals `float | None`), `RankedCandidate`, `RetrievalTrace` (shape only), `SearchOutcome`, `Explanation`, `SearchSession` + `SearchTurnRecord`.
- **Done when:**
  - Missing semantic score serializes as `null` and never as `0`; tests prove it.
- **Status:** [ ]

### P01.T05 — Error hierarchy
- **Skills:** domain-modeling
- **Depends on:** P01.T01
- **Files:** src/music_discovery/domain/errors.py, tests/unit/domain/test_errors.py
- **Do:**
  - Hierarchy from the skill; each class has a stable `code` and optional `details`.
- **Done when:**
  - All codes unique (test); every base §16 failure case maps to a class.
- **Status:** [ ]

### P01.T06 — Protocols & in-memory fakes
- **Skills:** domain-modeling, music-discovery-architecture
- **Depends on:** P01.T04, P01.T05
- **Files:** src/music_discovery/domain/protocols.py, tests/fakes/*.py, tests/unit/fakes/test_fakes_conform.py
- **Do:**
  - Protocols: `TrackRepository`, `ReleaseRepository`, `ArtistRepository`, `MatchRepository`, `SessionRepository`, `FeedbackRepository`, `EmbeddingStore`, `VectorIndex`, `LexicalIndex`, `TextEncoder`, `AudioEncoder`, `AudioProbe`, `StructuredLLM`, `SpatialRepository`, `Clock`, `IdGenerator`.
  - In-memory fakes for each (`FakeEncoder` produces deterministic hashed unit vectors).
- **Done when:**
  - `isinstance(fake, Protocol)` checks via `runtime_checkable` (or mypy structural checks) pass for every fake.
- **Status:** [ ]

### P01.T07 — SQLite persistence for catalog repositories
- **Skills:** domain-modeling, music-discovery-architecture
- **Depends on:** P01.T06, P00.T02
- **Files:** src/music_discovery/infrastructure/database.py, src/music_discovery/infrastructure/repositories.py, tests/integration/infrastructure/test_repositories.py
- **Do:**
  - SQLAlchemy Core tables: tracks, artists, labels, releases, track_artists, track_labels, external_ids, track_audio, relationships, cross_source_matches, import_runs; `schema_version` table; `init_db()`.
  - Repository implementations of the catalog protocols; upsert semantics; transactions per unit of work.
  - Lists (genres/styles) normalized into tables or JSON columns — document choice.
- **Done when:**
  - Same contract test suite runs against the fake and the SQL implementation (parametrized) and passes.
  - Re-upserting the same entity is idempotent.
- **Status:** [ ]

## Exit criteria
- [ ] `mypy --strict` passes on `domain/`.
- [ ] Repository contract tests pass for fake + SQL implementations.
- [ ] No domain module imports anything outside stdlib/pydantic/numpy (boundary check).
