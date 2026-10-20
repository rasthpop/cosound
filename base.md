# Semantic Music Discovery — Architecture and Implementation Plan

## 1. Project Objective

Build a natural-language music discovery system inspired by [Zigzag](https://www.reddit.com/r/TheOverload/comments/1pjfpf1/we_built_zigzag_a_spatial_interface_for_nonlinear/).

A user enters a request such as:

> Something chill with a flute.

The system interprets the request, retrieves relevant tracks using a hybrid retrieval engine, ranks the candidates, and returns a curated plate of tracks. Each result contains track metadata, a short evidence-grounded description, a relevance explanation, and available listening links.

The same catalog is projected into a nonlinear 2D space using UMAP. The visualization is a separate consumer of the discovery API and must not contain search, ranking, or agent logic.

### Core requirements

1. Natural-language requests, including subjective descriptions of sound and mood.
2. Discogs-based music metadata and artist, label, and release relationships.
3. CLAP-based text-to-audio semantic retrieval.
4. Hybrid retrieval combining audio similarity and catalog metadata.
5. Three logical agents: A (query understanding), B (discovery and ranking), C (feedback and explanation).
6. A stable UMAP projection of the music catalog.
7. A deck.gl-compatible spatial data API.
8. A small, reproducible evaluation using approximately 20 FMA audio examples.
9. Clear separation between domain logic, infrastructure, API, and interface components.
10. No dependence on any particular visual style, color palette, or layout.

---

## 2. Technical Resources

Use the following resources as the primary implementation references.

| Resource | Responsibility |
|---|---|
| [Discogs API](https://www.discogs.com/developers) | Music metadata, release information, artists, labels, genres, styles, and relationships |
| [LAION-AI/CLAP](https://github.com/LAION-AI/CLAP) | Audio and text embeddings for semantic retrieval |
| [FMA dataset](https://github.com/mdeff/fma) | Small, reproducible audio evaluation corpus |
| [UMAP documentation](https://umap-learn.readthedocs.io/en/latest/) | Dimensionality reduction for the spatial music catalog |
| [deck.gl examples](https://deck.gl/examples) | Reference implementations for interactive point visualization |
| [deck.gl ScatterplotLayer](https://deck.gl/docs/api-reference/layers/scatterplot-layer) | Rendering track nodes and selecting individual tracks |
| [deck.gl interactivity](https://deck.gl/next/docs/developer-guide/interactivity) | Click, hover, and object-picking integration |

### Critical distinction between metadata and audio

Discogs is the primary catalog source, but it is not an audio hosting or audio embedding service. Discogs metadata alone cannot establish that a recording sounds chill or contains a flute.

Implement two separate data sources:

- **Catalog source:** Discogs records, releases, artists, labels, genres, styles, years, track listings, and relationships.
- **Audio source:** locally available, legally usable audio files for which CLAP embeddings can be computed.

Do not assume that a Discogs release has a corresponding audio file. Do not scrape or download copyrighted recordings from Discogs.

Use FMA as the initial audio corpus. Its metadata and audio can be joined by FMA track ID. Discogs records can be associated with FMA tracks only when a reliable match is available. Do not manufacture associations based solely on similar titles or artist names.

The application must support catalog records without audio. Such records can participate in metadata-based retrieval but cannot receive a genuine audio-semantic score until audio is available.

---

## 3. Architecture Overview

Use a backend-first architecture with explicit service boundaries.

```text
                         USER REQUEST
                              |
                              v
                     API / Application Layer
                              |
                              v
                    Agent A: Query Understanding
                              |
                              v
                     Search Query Specification
                              |
                              v
                    Hybrid Retrieval Engine
                      /        |         \
                     v         v          v
                 Metadata    CLAP      Catalog
                 Search     Search    Relationships
                      \        |         /
                       \       |        /
                        Candidate Pool
                              |
                              v
                    Agent B: Discovery and Ranking
                              |
                              v
                       Ranked Track Plate
                              |
                              v
                    Agent C: Feedback and
                         Explanation
                              |
                 +------------+------------+
                 |                         |
                 v                         v
            Search Results            Search State
                 |                         |
                 v                         |
           Interface Layer <---------------+
                 |
                 v
           deck.gl Track Map

Separate offline pipeline:
Discogs + FMA Audio
        |
        v
Catalog Normalization
        |
        v
Audio Embeddings + Metadata Index
        |
        v
Track Similarity / Feature Matrix
        |
        v
UMAP Projection
        |
        v
Persisted Spatial Coordinates
```

### Architectural rules

- Agents orchestrate domain services; they do not implement data access, ranking algorithms, or database operations themselves.
- The retrieval engine must be usable without an LLM.
- Every important operation must have a deterministic Python implementation and an independently testable contract.
- Agent outputs must use validated schemas.
- The interface must consume API responses rather than importing backend domain logic.
- UMAP is an offline or explicitly scheduled data-processing operation, not part of each search request.
- Search and feedback must operate without deck.gl being mounted.
- The backend must not depend on frontend state, React components, or browser APIs.

---

## 4. Recommended Project Structure

Use Python for the backend and ML pipeline, and TypeScript for the frontend integration layer. FastAPI is the backend API framework.

```text
semantic-music-discovery/
├── pyproject.toml
├── README.md
├── .env.example
├── data/
│   ├── raw/
│   ├── processed/
│   ├── embeddings/
│   ├── indexes/
│   └── evaluation/
├── artifacts/
│   ├── umap/
│   └── evaluation/
├── src/
│   └── music_discovery/
│       ├── domain/
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── errors.py
│       │   └── protocols.py
│       ├── ingestion/
│       │   ├── discogs_client.py
│       │   ├── fma_loader.py
│       │   ├── normalizer.py
│       │   └── catalog_importer.py
│       ├── audio/
│       │   ├── clap_encoder.py
│       │   ├── embedding_store.py
│       │   └── audio_features.py
│       ├── retrieval/
│       │   ├── metadata_retriever.py
│       │   ├── semantic_retriever.py
│       │   ├── hybrid_retriever.py
│       │   ├── candidate_merger.py
│       │   └── ranker.py
│       ├── agents/
│       │   ├── agent_a_query.py
│       │   ├── agent_b_discovery.py
│       │   ├── agent_c_feedback.py
│       │   └── orchestrator.py
│       ├── descriptions/
│       │   ├── evidence_builder.py
│       │   └── description_service.py
│       ├── spatial/
│       │   ├── feature_builder.py
│       │   ├── umap_projector.py
│       │   └── spatial_repository.py
│       ├── application/
│       │   ├── search_service.py
│       │   ├── feedback_service.py
│       │   ├── track_service.py
│       │   └── map_service.py
│       ├── infrastructure/
│       │   ├── database.py
│       │   ├── repositories.py
│       │   ├── vector_index.py
│       │   └── settings.py
│       └── api/
│           ├── app.py
│           ├── dependencies.py
│           └── routes/
│               ├── search.py
│               ├── tracks.py
│               ├── feedback.py
│               └── map.py
├── frontend/
│   └── src/
│       ├── api/
│       │   ├── client.ts
│       │   └── types.ts
│       ├── hooks/
│       │   ├── useMusicSearch.ts
│       │   ├── useTrackDetails.ts
│       │   ├── useTrackFeedback.ts
│       │   └── useMusicMap.ts
│       ├── components/
│       │   └── [implemented in the separate UI plan]
│       └── pages/
├── scripts/
│   ├── import_discogs.py
│   ├── import_fma.py
│   ├── build_embeddings.py
│   ├── build_indexes.py
│   ├── build_map.py
│   └── evaluate.py
└── tests/
    ├── unit/
    ├── integration/
    ├── api/
    └── evaluation/
```

This structure is a logical boundary plan, not a requirement to create empty modules for every directory immediately. Implement the minimal vertical slice first, but preserve these responsibilities.

---

## 5. Domain Model

Define domain models before implementing the agents.

### 5.1 Track

A track represents a searchable recording or track listing. It is not necessarily identical to a physical Discogs release.

Required fields:

```text
Track
- id: string
- title: string
- artists: list[ArtistReference]
- release_id: optional string
- master_release_id: optional string
- year: optional integer
- genres: list[string]
- styles: list[string]
- labels: list[LabelReference]
- duration_seconds: optional float
- discogs_url: optional URL
- audio_source: optional string
- audio_path: optional string
- preview_url: optional URL
- metadata_confidence: optional float
- audio_embedding_id: optional string
- spatial_x: optional float
- spatial_y: optional float
```

Use stable internal IDs. Preserve external identifiers separately.

A Discogs release can contain multiple tracks, and different releases can contain versions of the same recording. Do not blindly treat each physical release as a unique musical recording.

For the initial prototype, use a single searchable `Track` abstraction with optional release and master-release relationships. Implement richer recording/version deduplication only when sufficient evidence exists.

### 5.2 Supporting entities

```text
Artist
- id
- external_id
- name
- aliases

Label
- id
- external_id
- name

Release
- id
- external_id
- title
- year
- genres
- styles
- track_listing

TrackAudio
- track_id
- source
- file_path
- duration_seconds
- sample_rate
- embedding_model
- embedding_version
- embedding_path

TrackRelationship
- source_track_id
- target_track_id
- relationship_type
- evidence_source
```

Use a repository interface so services do not depend on a particular SQL library.

### 5.3 Search specification

Agent A must output a validated structure rather than arbitrary prose.

```json
{
  "original_query": "Something chill with a flute",
  "mood_preferences": [
    {
      "value": "chill",
      "weight": 0.7
    }
  ],
  "instrument_preferences": [
    {
      "value": "flute",
      "weight": 1.0
    }
  ],
  "genre_preferences": [],
  "tempo_preferences": [],
  "vocal_preferences": "unspecified",
  "hard_constraints": [],
  "negative_preferences": [],
  "reference_track_ids": [],
  "diversity": 0.5,
  "needs_clarification": false,
  "uncertainties": []
}
```

This is an example schema. The exact fields and validation rules should be implemented in Pydantic.

Do not interpret every noun phrase as a hard constraint. “Something chill with a flute” expresses a strong instrumentation preference and a mood preference; it does not necessarily prohibit every track that has additional instruments.

Explicit constraints such as “instrumental only” should be represented separately from soft preferences.

---

## 6. Agent A — Query Understanding

### Responsibility

Convert a natural-language request into a normalized, machine-readable `SearchSpecification`.

Agent A must not retrieve tracks, calculate embeddings, or rank results.

### Input

```text
User query
Optional conversation/search state
Optional previous feedback
```

### Processing

1. Identify musical attributes: mood, instruments, genre, tempo, energy, vocals, era, and sonic texture.
2. Normalize synonyms, such as “laid-back” and “relaxed.”
3. Separate hard constraints from soft preferences.
4. Preserve the original request.
5. Represent ambiguity and uncertainty explicitly.
6. Decide whether clarification is necessary.

Use a configurable LLM with structured output if available. A deterministic parser and synonym dictionary must remain a fallback.

### Output

A validated `SearchSpecification`.

### Rules

- Never invent a track, artist, or catalog entry.
- Never claim that an instrument has been detected from the text alone.
- Do not ask a clarification question when the request is broad but still actionable.
- Ask for clarification only when ambiguity materially prevents useful retrieval.
- Do not call Discogs or CLAP directly from the agent.

### Evaluation

Create labeled query examples with expected attributes and constraint classifications.

Measure:

- Attribute extraction precision, recall, and F1.
- Hard-constraint classification accuracy.
- Structured-output validity.
- Agreement between the parsed request and human judgments.

The first evaluation set should include the 20 evaluation queries described in Section 12, with additional examples added only when needed to test parser edge cases.

---

## 7. Agent B — Discovery and Ranking

### Responsibility

Coordinate retrieval, combine candidates, rank tracks, and return a diverse set of relevant candidates.

Agent B should primarily orchestrate deterministic retrieval services. Do not require an LLM to calculate similarity scores.

### Pipeline

```text
SearchSpecification
       |
       v
HybridRetriever
       |
       +--> MetadataRetriever
       |
       +--> SemanticRetriever
       |
       +--> RelationshipRetriever (optional)
       |
       v
CandidateMerger
       |
       v
Hard Constraint Filtering
       |
       v
Score Normalization
       |
       v
Hybrid Ranker
       |
       v
Diversity Reranking
       |
       v
Ranked Candidate Set
```

### 7.1 MetadataRetriever

Use the local normalized catalog as the primary query-time data source.

Search over:

- Track and release titles.
- Artist names and aliases.
- Genres and styles.
- Label names.
- Release years.
- Track listings and available descriptive metadata.

Discogs is a catalog source, not a real-time search dependency for every user request. Import and cache data in accordance with Discogs API terms.

Support filtering and lexical matching, but do not assume that genre/style tags encode every audible attribute.

### 7.2 SemanticRetriever

Use CLAP to compare user text with precomputed audio embeddings.

Reference: https://github.com/LAION-AI/CLAP

Responsibilities:

1. Load one explicitly configured pretrained checkpoint.
2. Generate the text embedding for the query or its semantic prompts.
3. Retrieve nearest audio embeddings.
4. Return track IDs and raw similarity scores.
5. Record the model/checkpoint version.

Use the same compatible CLAP checkpoint and embedding configuration when generating audio and text representations.

Do not recompute the audio embedding for every search request.

For a track without an audio embedding, return no semantic score. Do not replace a missing score with zero and then interpret zero as evidence of irrelevance.

Use a simple exact cosine-similarity search initially. For a small catalog, FAISS or a NumPy implementation is sufficient. Keep the vector-index implementation behind an interface so it can be replaced later.

### 7.3 Query expansion

For subjective requests, Agent B may request a small set of controlled semantic prompts from Agent A or a deterministic prompt builder.

For example:

```text
Original query:
"Something chill with a flute"

Expansion prompts:
- Relaxed instrumental music featuring a flute melody.
- Calm ambient music with soft woodwind textures.
- Laid-back electronic music with a flute sample.
```

Treat expansions as alternate retrieval queries, not as additional requirements. Avoid generating so many paraphrases that the original user intent is diluted.

### 7.4 CandidateMerger

Merge the results from metadata and semantic retrieval.

Requirements:

- Deduplicate by internal track ID.
- Preserve the score and source rank from each retriever.
- Preserve retrieval provenance.
- Handle candidates missing from one source.
- Keep enough candidates for ranking and diversity selection.

Start with a candidate pool of approximately 50–100 tracks where the catalog permits it. For the 20-example evaluation, use smaller pools if necessary and document the limits.

### 7.5 HybridRanker

Use a transparent baseline ranking function:

\[
S(t,q)=w_sS_{\text{semantic}}+
w_mS_{\text{metadata}}+
w_rS_{\text{relationship}}
\]

Where:

- \(S_{\text{semantic}}\): normalized text-to-audio similarity.
- \(S_{\text{metadata}}\): lexical and metadata compatibility.
- \(S_{\text{relationship}}\): optional relevance from artist, label, or release relationships.

Begin with semantic and metadata retrieval. Include the relationship score only after implementing and testing it.

Weights are configuration parameters, not hard-coded truths. Calibrate score normalization and weights on the validation portion of the evaluation set. Do not tune them against test judgments.

Missing modalities must be handled explicitly. Renormalize weights over available signals or use a documented fallback. A track with no audio must not automatically receive the same treatment as a track whose audio has been evaluated and found irrelevant.

Hard constraints must be enforced independently of the weighted score when reliable evidence is available.

For example, if the user explicitly requires instrumental music, tracks known to contain vocals should be excluded. If vocal evidence is missing, represent that uncertainty rather than treating missing metadata as proof of compliance.

### 7.6 Diversity reranking

Avoid returning multiple near-identical releases or versions when the user wants to discover music.

Implement a simple diversity-aware reranker, such as maximal marginal relevance (MMR), after relevance ranking.

Use the relevance score and inter-track similarity to balance:

- Relevance to the original query.
- Novelty relative to already selected tracks.
- Coverage of different musical interpretations.

Make the diversity parameter configurable. The first result should generally be the strongest match, while later results can explore related directions.

### Output

A ranked candidate set with scores, retrieval provenance, track metadata, and evidence references.

Agent B must not generate unsupported descriptions.

---

## 8. Agent C — Feedback and Explanation

### Responsibility

Interpret user feedback, update search state, and create short evidence-grounded explanations for returned tracks.

Agent C must not modify the catalog or audio embeddings.

### Feedback types

```text
MORE_LIKE_THIS
LESS_LIKE_THIS
NOT_RELEVANT
WRONG_INSTRUMENT
MORE_OF_ATTRIBUTE
LESS_OF_ATTRIBUTE
SELECT_TRACK
```

Store feedback with:

```text
FeedbackEvent
- event_id
- search_session_id
- query_id
- track_id
- event_type
- attribute
- value
- timestamp
```

### Feedback workflow

1. Receive a feedback event and the current search state.
2. Interpret the event as a preference update.
3. Produce a revised `SearchSpecification` or updated ranking preferences.
4. Run retrieval and ranking again.
5. Preserve the original query and feedback history.
6. Return the updated plate and an explanation of what changed.

Example:

User: “Something chill with a flute.”

Feedback: “More electronic, less acoustic.”

The revised query should increase the preference for electronic textures while preserving the flute and chill requirements.

Do not silently discard previous constraints when interpreting new feedback.

### Explanation generation

For each candidate, construct an evidence object from known information:

```text
TrackEvidence
- metadata_matches
- genre_matches
- style_matches
- semantic_score
- retrieval_sources
- known_audio_features
- uncertainty_flags
```

Generate a one- or two-sentence explanation from that evidence.

Example:

> A relaxed electronic track with flute-like melodic textures and a restrained rhythmic arrangement. It matches the requested mood and has a strong semantic match to the flute-oriented description.

The example is illustrative. A real response must only make claims supported by the track's evidence.

Do not present a CLAP similarity score as a probability or as definitive proof of instrument presence.

When evidence is insufficient, use a cautious explanation or omit the unsupported claim.

### Evaluation

- Feedback interpretation accuracy.
- Preservation of existing constraints.
- Ranking improvement after relevant feedback.
- Description factuality, assessed against track evidence.
- User preference satisfaction before and after refinement.

For the initial implementation, use a deterministic feedback update mechanism. An LLM may normalize free-text feedback into the same validated feedback schema.

---

## 9. Hybrid Retrieval and Audio Embedding Pipeline

### 9.1 Offline audio processing

Create a repeatable script to process the available FMA audio files.

Steps:

1. Read the evaluation dataset manifest.
2. Validate that each audio file exists and can be decoded.
3. Load the configured CLAP model/checkpoint.
4. Apply the preprocessing required by the selected checkpoint.
5. Generate audio embeddings.
6. Save embeddings keyed by stable FMA track IDs.
7. Store the model version and preprocessing configuration.
8. Report failures and missing files.
9. Build the vector index.

Keep raw audio, metadata, embeddings, and evaluation judgments in separate locations.

Never use an embedding produced by one checkpoint as though it were compatible with a different checkpoint.

### 9.2 Embedding representation

Use normalized floating-point vectors where supported by the model's embedding interface.

Cosine similarity:

\[
\operatorname{sim}(x,y)=
\frac{x^\top y}{\|x\|_2\|y\|_2}
\]

Normalize vectors consistently. Handle zero vectors and invalid embeddings as errors.

### 9.3 Audio feature extraction

For the MVP, CLAP is the main semantic audio signal.

Optionally add interpretable acoustic features such as:

- Estimated tempo.
- RMS energy.
- Spectral centroid.
- Spectral rolloff.
- Onset strength.

These features are auxiliary signals. They do not independently prove that a track is chill or contains a flute.

Do not add an instrument classifier until there is a clear need and an appropriate evaluation method.

### 9.4 Semantic search fallback

If a track has metadata but no audio:

- Allow metadata retrieval.
- Return its catalog information and source link.
- Mark its audio analysis as unavailable.
- Do not claim that its audio was semantically matched.

If no candidates satisfy the reliable hard constraints, return an explicit no-confident-match state rather than silently relaxing the constraints.

---

## 10. Discogs Ingestion and Catalog Management

### 10.1 API integration

Implement a dedicated `DiscogsClient`.

Responsibilities:

- Authentication configuration.
- Request construction.
- Response validation.
- Pagination.
- Retry and backoff for transient failures.
- Rate-limit handling.
- Request logging.
- Error classification.

Use the official Discogs API documentation:

https://www.discogs.com/developers

Read the current API terms, attribution requirements, rate limits, and data-use restrictions before importing or caching records.

Never bypass rate limits or attempt to reproduce the full Discogs service. Use a deliberately scoped import.

### 10.2 Import strategy

Do not attempt to download the entire Discogs catalog for this prototype.

Start with a bounded selection of records based on relevant genres/styles, labels, artists, and releases. The selection must be configurable and reproducible.

Store:

- Discogs release ID.
- Master release ID where available.
- Artist and label identifiers.
- Genre and style tags.
- Release year.
- Track listing.
- Source URL.
- Import timestamp.

Track listings, artist credits, and master-release relationships should be preserved rather than flattened into a single title string.

### 10.3 Relationship graph

Use catalog relationships as a secondary discovery mechanism.

Potential connections:

- Same artist.
- Same label.
- Same master release.
- Same release series or compilation, when supported by reliable data.
- Shared genres and styles.

Do not interpret these relationships as proof of audio similarity. They are context for discovery and a possible ranking signal.

### 10.4 Audio matching

Match FMA records to Discogs records only when there is reliable evidence.

A match may use normalized title, artist name, duration, release information, and other available identifiers. Ambiguous matches must remain unresolved.

Preserve provenance and confidence for every cross-source association.

Do not assume that the FMA track ID and Discogs release ID refer to the same entity.

---

## 11. UMAP Spatial Projection

### Responsibility

Create a stable two-dimensional projection of the available catalog. The backend exposes coordinates; the frontend renders them.

Reference: https://umap-learn.readthedocs.io/en/latest/

### 11.1 Input features

Use audio embeddings as the primary feature space for tracks with audio.

Optionally create a combined representation incorporating metadata, but treat this as a separate experiment. Do not concatenate arbitrary text, categorical IDs, and audio embeddings without a deliberate normalization and weighting strategy.

For tracks without audio, either:

1. Exclude them from the audio-semantic projection; or
2. Place them in a separate metadata-only projection.

Do not pretend that metadata-only and audio-semantic coordinates have identical meaning.

For the MVP, use one stable audio-based projection for all tracks with embeddings.

### 11.2 Projection process

1. Load the persisted embedding matrix.
2. Align rows with stable track IDs.
3. Validate dimensions and finite values.
4. Configure UMAP with two output dimensions.
5. Set a fixed random seed and explicit parameters.
6. Fit the projection.
7. Persist the coordinates and projection metadata.
8. Expose the coordinates through the map API.

Example configuration:

```python
import umap

projector = umap.UMAP(
    n_components=2,
    n_neighbors=15,
    min_dist=0.1,
    metric="cosine",
    random_state=42,
    transform_seed=42,
)
```

Treat these as initial values, not optimal settings. Evaluate neighborhood preservation and inspect whether the projection is useful for exploration.

### 11.3 Projection persistence

Persist:

- Track IDs and their row order.
- Embedding model/checkpoint identifier.
- Embedding preprocessing version.
- UMAP parameters.
- Random seed.
- Package version.
- Projection generation timestamp.
- Final coordinates.

Do not regenerate the whole map after each search.

When the catalog changes, explicitly rebuild the projection or use a compatible fitted projection to transform new points. UMAP's `transform` method can project new data into a fitted embedding, but the result and its limitations must be tested before using it in production.

### 11.4 Interpretation

UMAP coordinates are visualization coordinates, not geographic locations and not calibrated distances.

The map should help reveal neighborhoods and support exploration. It must not be treated as a replacement for the retrieval engine.

A track being close to another point on the 2D map does not guarantee that the two tracks are highly similar in the original embedding space.

---

## 12. Evaluation Dataset: 20 FMA Examples

The evaluation must be small, reproducible, and separate from the Discogs catalog ingestion process.

Use approximately 20 FMA tracks as the initial evaluation corpus. The FMA repository documents the dataset and its audio and metadata subsets:

https://github.com/mdeff/fma

Use the official metadata and the corresponding audio subset. Verify the selected audio files and their usage terms before running the experiment.

### 12.1 Selection strategy

Choose 20 valid tracks, preferably spanning multiple available genres and acoustic characteristics.

Do not select only tracks that match the target queries. Include challenging negatives.

Create a manifest:

```text
data/evaluation/fma_20_manifest.csv
```

Suggested columns:

```text
fma_track_id
title
artist
genre
audio_path
source
license
split
```

The manifest must be generated once, saved, and reused. Do not randomly choose new tracks on every evaluation run.

### 12.2 Query set

Create 20 natural-language queries.

Include examples such as:

```text
1. Something chill with a flute.
2. Dark electronic music with a heavy bassline.
3. Dreamy music with female vocals.
4. Warm, relaxed jazz.
5. Fast music with aggressive percussion.
6. Calm acoustic music without vocals.
7. Atmospheric music with a gradual build.
8. Something playful and rhythmically unusual.
9. Minimal electronic music with repetitive rhythms.
10. Melancholic music with soft piano.
```

Expand the set to 20 with diverse requests and controlled variations in phrasing.

Do not assume that every query has a valid match in the 20-track corpus. Record the availability of relevant examples.

### 12.3 Relevance judgments

For each query-track pair, record human relevance judgments.

Use a small ordinal scale:

```text
3 = Strong match
2 = Good match
1 = Partial match
0 = Not relevant
```

For requests containing an instrument or a strict constraint, also record separate fields:

```text
instrument_present: yes / no / uncertain
mood_relevance: 0–3
constraint_satisfied: yes / no / unknown
overall_relevance: 0–3
```

Do not label instrument presence based only on CLAP's output. Listen to the available audio and record the basis for the judgment.

If there is no reliable audio evidence, mark the instrument label as uncertain.

### 12.4 Evaluation splits

With only 20 tracks, do not claim that the dataset supports reliable model training.

Use the corpus for a small retrieval benchmark.

If tuning weights, divide the queries into:

- Development/validation: 10 queries.
- Test: 10 queries.

Keep all judgments for the same query in the same split.

Use a fixed, documented split. Because the dataset is very small, report the number of queries and the limitations of the results.

Do not train or fine-tune CLAP on these examples. The initial objective is to evaluate a pretrained model and a hybrid retrieval strategy.

### 12.5 Baselines

Evaluate three approaches on the same queries and corpus.

**Baseline A — Metadata-only retrieval**

Use titles, artists, genres, styles, and any relevant catalog metadata.

**Baseline B — CLAP-only retrieval**

Rank tracks using text-to-audio cosine similarity.

**Proposed — Hybrid retrieval**

Combine metadata and CLAP retrieval, apply hard constraints where reliable evidence exists, and use the hybrid ranker.

Use the same catalog and relevance judgments for all systems.

### 12.6 Metrics

Calculate:

- Recall@5.
- Precision@5.
- nDCG@5.
- Hard-constraint satisfaction rate.
- Mean reciprocal rank for queries with at least one relevant track.

Use the ordinal judgments when calculating nDCG.

When the corpus contains no relevant result for a query, report that query separately instead of interpreting a low score as a normal ranking failure.

Also report:

- Number of tracks with valid audio.
- Number of tracks with valid embeddings.
- Number of queries with at least one relevant candidate.
- Number of failed or skipped queries.
- Per-query ranking results.

Twenty tracks is a smoke-test corpus, not sufficient evidence of general retrieval quality. The evaluation should demonstrate the workflow and identify failure cases, not make broad claims about performance.

### 12.7 Additional component evaluations

**Agent A**

Evaluate attribute extraction and constraint classification against manually prepared labels.

**Agent B**

Compare metadata-only, CLAP-only, and hybrid rankings.

**Agent C**

Use a small set of predefined feedback examples. Measure whether relevant feedback improves ranking and whether descriptions are supported by the evidence.

**UMAP**

Measure neighborhood preservation where practical and manually inspect whether obvious near-neighbors remain near each other. Do not use visual attractiveness as the only success criterion.

**Descriptions**

Manually check every generated description in the small evaluation run for unsupported instrument, mood, or genre claims.

### 12.8 Evaluation output

Write results to:

```text
artifacts/evaluation/
├── manifest.csv
├── queries.jsonl
├── judgments.csv
├── per_query_results.csv
├── metrics.json
├── comparison.csv
└── report.md
```

The report must contain:

- Dataset composition.
- Model and checkpoint versions.
- Retrieval configuration.
- Evaluation split.
- Metric definitions.
- Results for all baselines.
- Per-query failures.
- Known limitations.
- Reproduction instructions.

---

## 13. Backend API Contracts

The API layer is a thin transport layer over application services.

Use Pydantic schemas for validation. Do not expose internal database models directly.

### 13.1 Search

`POST /api/search`

Request:

```json
{
  "query": "Something chill with a flute",
  "limit": 8,
  "session_id": null
}
```

Response:

```json
{
  "query_id": "query-id",
  "session_id": "session-id",
  "interpreted_query": {
    "mood_preferences": ["chill"],
    "instrument_preferences": ["flute"],
    "hard_constraints": []
  },
  "results": [
    {
      "track_id": "track-id",
      "title": "Track title",
      "artists": ["Artist name"],
      "score": 0.82,
      "score_breakdown": {
        "semantic": 0.84,
        "metadata": 0.76,
        "relationship": null
      },
      "description": "Evidence-grounded description.",
      "match_reasons": ["Strong semantic match"],
      "genres": [],
      "styles": [],
      "discogs_url": null,
      "preview_url": null,
      "audio_available": true,
      "evidence_status": "audio_and_metadata"
    }
  ]
}
```

All IDs and values above are illustrative.

The API must preserve missing values as null or explicit status fields. Do not fabricate preview URLs or metadata.

### 13.2 Track details

`GET /api/tracks/{track_id}`

Returns:

- Track metadata.
- Artists and release information.
- Available listening links.
- Audio-analysis availability.
- Known relationships.
- Spatial coordinates, if available.

### 13.3 Feedback

`POST /api/feedback`

Request:

```json
{
  "session_id": "session-id",
  "query_id": "query-id",
  "track_id": "track-id",
  "event_type": "MORE_OF_ATTRIBUTE",
  "attribute": "electronic",
  "value": true
}
```

Response:

```json
{
  "accepted": true,
  "updated_search_state": {},
  "next_action": "REFINE_SEARCH"
}
```

The API must validate that the feedback refers to a valid search session and track.

### 13.4 Map points

`GET /api/map/points`

Query parameters:

```text
limit
cursor
genre
style
artist_id
has_audio
```

Response:

```json
{
  "points": [
    {
      "track_id": "track-id",
      "x": -2.4,
      "y": 1.8,
      "title": "Track title",
      "artist": "Artist name",
      "genre": "Electronic",
      "style": "Ambient",
      "discogs_url": null
    }
  ],
  "next_cursor": null,
  "projection_version": "umap-v1"
}
```

Use pagination or bounded retrieval for larger catalogs. Do not send full embedding vectors to the frontend.

### 13.5 Map neighbors

`GET /api/tracks/{track_id}/neighbors`

Returns the nearest tracks according to the original embedding space or a clearly specified relationship metric.

Use the original embedding space for actual nearest-neighbor recommendations. Do not compute recommendations solely from 2D UMAP distances.

---

## 14. Frontend Separation: View / Hook Pattern

The visual interface will be specified in a separate plan. This section defines the integration boundary only.

Use a React-style View / Hook pattern.

### 14.1 API client

`frontend/src/api/client.ts`

Responsibilities:

- Typed HTTP requests.
- Request cancellation.
- Error normalization.
- Base URL configuration.
- Serialization and deserialization.

It must not contain ranking logic, CLAP logic, or business rules.

### 14.2 API types

`frontend/src/api/types.ts`

Define TypeScript interfaces corresponding to the public API contracts.

Keep them synchronized with backend schemas. Prefer generated OpenAPI types if that can be introduced without unnecessary complexity.

### 14.3 Hooks

`useMusicSearch`

Responsibilities:

- Submit search requests.
- Expose loading, error, and result state.
- Support cancellation or stale-response protection.
- Retain the active query/session IDs.
- Expose a method to refresh results after feedback.

`useTrackDetails`

Responsibilities:

- Fetch track details.
- Expose loading and error states.
- Cache details when appropriate.

`useTrackFeedback`

Responsibilities:

- Submit typed feedback events.
- Track submission state.
- Return the updated search state or refreshed results.

`useMusicMap`

Responsibilities:

- Fetch map points.
- Expose map loading/error state.
- Support filtering and pagination.
- Expose selected track IDs and callbacks.
- Remain independent of deck.gl.

The hook must not calculate UMAP coordinates or track similarities.

### 14.4 View components

Views receive data and callbacks from hooks or their parent containers.

They should not:

- Call Discogs directly.
- Load CLAP.
- Compute embeddings.
- Interpret natural-language queries.
- Implement ranking.
- Mutate the catalog.
- Run UMAP.

The map renderer receives an array of points and emits events such as `onTrackSelect(trackId)`. A parent controller can pass the selected ID to track details or the search service.

Use deck.gl's `ScatterplotLayer` as the initial point renderer. The layer should receive precomputed coordinates and stable track identifiers.

This design allows the visual presentation, color system, animation, and atmosphere to change without changing the backend or retrieval pipeline.

---

## 15. Configuration and Secrets

Use environment-based configuration.

Example `.env.example`:

```text
APP_ENV=development
DATABASE_URL=sqlite:///./music_discovery.db

DISCOGS_USER_AGENT=SemanticMusicDiscovery/0.1
DISCOGS_TOKEN=

CLAP_CHECKPOINT=
CLAP_MODEL_VERSION=

DATA_DIR=./data
ARTIFACTS_DIR=./artifacts

UMAP_RANDOM_STATE=42
UMAP_N_COMPONENTS=2
```

Never commit actual credentials or access tokens.

Do not hard-code local audio paths into source code. Use a configurable data directory and a dataset manifest.

Record configuration versions alongside embeddings, indexes, projections, and evaluation results.

---

## 16. Error Handling and Reliability

Implement explicit handling for:

- Discogs rate limiting and unavailable responses.
- Missing metadata.
- Missing or corrupt audio.
- CLAP model loading failures.
- Invalid embeddings.
- Missing vector-index entries.
- No relevant candidates.
- Invalid agent output.
- Invalid or contradictory hard constraints.
- UMAP artifact mismatch.
- Stale frontend requests.
- Invalid feedback events.

An external service failure must not corrupt locally stored catalog data.

The system should degrade gracefully. If CLAP is unavailable, metadata-only search may still work, but the response must indicate that semantic audio retrieval was unavailable.

If the map projection is unavailable, search must still work.

If a description cannot be grounded in available evidence, return a conservative description or omit it.

---

## 17. Testing Strategy

### Unit tests

Test each functional module independently:

- Query schema validation.
- Query normalization.
- Hard-constraint handling.
- Metadata scoring.
- CLAP embedding normalization.
- Cosine similarity.
- Candidate merging.
- Missing-modality behavior.
- Hybrid score calculation.
- Diversity reranking.
- Feedback state updates.
- Description evidence validation.
- UMAP artifact validation.

Use small mocked datasets for unit tests.

### Integration tests

Test:

- Discogs response normalization with saved fixtures.
- FMA metadata/audio ID alignment.
- Embedding generation and persistence.
- Search against a real small local index.
- End-to-end search using all three agents.
- Feedback followed by a new search.
- Map point retrieval from persisted coordinates.

Do not require live Discogs access for every test. Use mocked HTTP responses or recorded fixtures, while ensuring the fixture use respects the source's terms.

### API tests

Verify:

- Request and response schemas.
- Invalid input handling.
- Empty results.
- Missing audio.
- Agent failures.
- Invalid track IDs.
- Feedback validation.
- Map pagination.

### Evaluation tests

Run the fixed 20-example evaluation and verify:

- All configured baselines run.
- Missing data is reported.
- Metrics are reproducible.
- Output artifacts are written.
- The final report identifies limitations.

---

## 18. Implementation Order

Implement in this order. Do not start by building all three agents and the map simultaneously.

### Milestone 1 — Domain and data ingestion

1. Define domain models and schemas.
2. Implement Discogs API client and a bounded importer.
3. Implement FMA manifest loading.
4. Normalize and persist metadata.
5. Add data provenance and audio availability fields.
6. Test track IDs and cross-source matching.

**Acceptance criterion:** a local catalog can be queried without a live Discogs request.

### Milestone 2 — CLAP and semantic retrieval

1. Select and document a compatible pretrained checkpoint.
2. Implement audio embedding generation.
3. Generate embeddings for the available evaluation audio.
4. Persist embeddings with model-version metadata.
5. Implement text embedding and cosine retrieval.
6. Test missing audio and invalid embedding handling.

**Acceptance criterion:** a text query retrieves ranked candidates from the local audio corpus.

### Milestone 3 — Hybrid retrieval

1. Implement metadata retrieval.
2. Implement candidate merging.
3. Implement score normalization.
4. Implement configurable hybrid ranking.
5. Add hard-constraint filtering.
6. Add diversity reranking.
7. Evaluate metadata-only, CLAP-only, and hybrid baselines.

**Acceptance criterion:** all three retrieval approaches run against the same catalog and can be compared.

### Milestone 4 — Agent orchestration

1. Implement Agent A with structured output.
2. Implement Agent B as a retrieval/ranking orchestrator.
3. Implement Agent C for feedback and grounded descriptions.
4. Add a shared search-session model.
5. Test multi-turn constraint preservation.

**Acceptance criterion:** a natural-language request produces a ranked plate, and feedback changes the next result set predictably.

### Milestone 5 — Spatial data pipeline

1. Build the feature matrix.
2. Generate a reproducible UMAP projection.
3. Persist coordinates and projection metadata.
4. Implement map-point and neighbor services.
5. Validate coordinate-to-track ID alignment.

**Acceptance criterion:** the backend returns stable map coordinates without recalculating UMAP during searches.

### Milestone 6 — API and interface integration

1. Implement FastAPI endpoints.
2. Define public API types.
3. Implement frontend API client.
4. Implement search, details, feedback, and map hooks.
5. Expose track selection events to the interface.
6. Add loading, error, and empty states.

**Acceptance criterion:** the interface can search, display a plate, submit feedback, and retrieve map points without implementing ML or retrieval logic.

### Milestone 7 — Evaluation and documentation

1. Finalize the 20-track manifest.
2. Finalize query and relevance judgments.
3. Run all baselines.
4. Evaluate all three agents.
5. Record failures and limitations.
6. Generate the evaluation report.
7. Document reproducible commands and configuration.

**Acceptance criterion:** a new developer can reproduce the small evaluation and understand how each component contributes to the final result.

---

## 19. Non-Goals for This Implementation

Do not implement these unless a later requirement explicitly requests them:

- Training a new audio foundation model.
- Fine-tuning CLAP.
- Downloading the entire Discogs database.
- Downloading arbitrary music from streaming services.
- Rebuilding UMAP on every search.
- Generating a full visual design system.
- Adding complex multi-agent debate or autonomous agent loops.
- Building a recommendation model trained on large-scale user behavior.
- Claiming that metadata proves audible instrumentation.
- Claiming that the 20-track evaluation demonstrates general production performance.

The architecture should remain extensible without requiring these capabilities in the MVP.

---

## 20. Definition of Done

The architecture implementation is complete when:

- [ ] Discogs metadata can be imported through a bounded, documented process.
- [ ] FMA audio and metadata can be loaded reproducibly.
- [ ] Cross-source matching preserves provenance and uncertainty.
- [ ] CLAP embeddings are generated and versioned.
- [ ] Metadata and semantic retrieval work independently.
- [ ] Hybrid ranking combines available signals safely.
- [ ] Hard constraints are handled independently of soft ranking preferences.
- [ ] Agent A returns validated query specifications.
- [ ] Agent B returns ranked, deduplicated, diverse candidates.
- [ ] Agent C updates search state from feedback and produces grounded descriptions.
- [ ] UMAP coordinates are generated and persisted outside the request path.
- [ ] The map API exposes coordinates without depending on deck.gl.
- [ ] The API exposes search, track details, feedback, and map data.
- [ ] Frontend hooks isolate API interaction from view components.
- [ ] The 20-example evaluation compares metadata-only, CLAP-only, and hybrid retrieval.
- [ ] Evaluation artifacts and a limitations report are generated.
- [ ] Tests cover the principal domain, retrieval, agent, API, and evaluation contracts.
- [ ] No API keys, unlicensed audio, fabricated links, or unsupported track claims are introduced.

**Primary engineering principle:** build a testable music-retrieval system first. The agents coordinate independent capabilities, the hybrid engine determines relevance, UMAP supplies spatial coordinates, and the interface only presents the resulting data and emits user actions.