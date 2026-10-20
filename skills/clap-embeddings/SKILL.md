---
name: clap-embeddings
description: CLAP text-to-audio embeddings for the music discovery system — choosing and pinning a checkpoint, the AudioEncoder/TextEncoder implementation, offline embedding generation with versioned metadata, the embedding store, the cosine vector index, and the SemanticRetriever with explicit missing-embedding handling. Load for anything in audio/, infrastructure/vector_index.py, retrieval/semantic_retriever.py, scripts/build_embeddings.py or scripts/build_indexes.py.
---

# CLAP Embeddings & Semantic Retrieval

Spec: `base.md` §7.2, §7.3, §9.1–9.4, §16. Reference: https://github.com/LAION-AI/CLAP.

## 1. Checkpoint decision (task P03.T01 — an ADR)

Write `docs/adr/0002-clap-checkpoint.md`. Candidates to evaluate (verify names and availability on the CLAP README / HF hub at decision time):

| Option | Package | Notes |
|---|---|---|
| `music_audioset_epoch_15_esc_90.14.pt` (amodel `HTSAT-base`) | `laion_clap` | music-specific LAION checkpoint — the default candidate |
| `music_speech_audioset_epoch_15_esc_89.98.pt` (`HTSAT-base`) | `laion_clap` | music + speech; may help vocal queries |
| `630k-audioset-best.pt` (`HTSAT-tiny`) | `laion_clap` | general audio; what `load_ckpt()` downloads by default |
| `laion/larger_clap_music` | `transformers` `ClapModel`/`ClapProcessor` | same family via HF; easier pinning, different preprocessing path |

Decide on: music-domain fit, license, reproducible download (pinned URL + SHA256), CPU inference speed for ~20–8000 clips, dependency footprint. Record `model_id` (e.g. `laion_clap/music_audioset_epoch_15_esc_90.14/HTSAT-base/fusion=false`), the file hash, and the package version. **Exactly one checkpoint is configured at a time** (`CLAP_CHECKPOINT`, `CLAP_MODEL_VERSION`).

## 2. Encoder (`audio/clap_encoder.py`)

Implements `domain.protocols.AudioEncoder` and `TextEncoder`. `laion_clap` sketch:

```python
import laion_clap
model = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-base")
model.load_ckpt(ckpt_path)                       # explicit path; never rely on implicit download in prod
audio = model.get_audio_embedding_from_filelist(x=[str(p) for p in paths], use_tensor=False)  # (n, 512)
text = model.get_text_embedding(prompts, use_tensor=False)                                     # (m, 512)
```

- Audio is expected at **48 kHz**; the file-list API resamples internally. If you load audio yourself (`get_audio_embedding_from_data`), resample to 48 kHz mono float32 and follow the README's quantization note (int16 round-trip) for parity with training.
- Lazily load the model on first use; loading failure raises `ModelLoadError` — callers degrade to metadata-only.
- Batch encode; `torch.no_grad()`; set `model.eval()`; seed and deterministic flags where cheap.
- Test single-item batches explicitly (some versions behave differently for batch size 1); if needed, batch-pad internally and slice.
- Expose `model_id` and `embedding_dim` properties. Pin `torch`, `laion_clap`, `numpy` versions in `pyproject.toml` — version drift silently changes embeddings.

## 3. Embedding normalization & validation

```python
def l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if not np.all(np.isfinite(x)): raise InvalidEmbedding("non-finite values")
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    if np.any(n < eps): raise InvalidEmbedding("zero vector")
    return x / n
```

Cosine similarity on normalized vectors is a dot product. Store **normalized float32**.

## 4. Offline generation (`scripts/build_embeddings.py`)

Steps (base §9.1): read manifest → validate each file (exists + decodes) → load configured checkpoint → encode in batches → normalize → persist → report → build index.

Persisted layout:

```
data/embeddings/{embedding_version}/
├── audio_embeddings.npy        # float32 (n, d), L2-normalized
├── track_ids.json              # row order, stable internal ids
├── meta.json                   # model_id, ckpt sha256, package versions, sample_rate,
│                               # preprocessing, created_at, manifest sha256, n, d, failures
└── failures.csv                # track_id, path, error_code, message
```

`embedding_version` = short hash of (model_id + preprocessing config). Re-running with identical inputs reproduces the same version dir (skip or `--force`).

## 5. Embedding store & vector index

- `audio/embedding_store.py` reads/writes the layout above and **refuses to load** when `meta.model_id` ≠ configured `CLAP_MODEL_VERSION` (`EmbeddingVersionMismatch`). Never mix checkpoints.
- `infrastructure/vector_index.py`: `NumpyCosineIndex` (exact, `scores = M @ q`, `argpartition` top-k) behind `domain.protocols.VectorIndex`. FAISS (`IndexFlatIP`) is an optional drop-in later. Index carries `model_id`; queries from a different model raise.
- `restrict_to` support so ranking can score a given candidate pool.

## 6. SemanticRetriever (`retrieval/semantic_retriever.py`)

```python
class SemanticRetriever:
    def __init__(self, text_encoder: TextEncoder, index: VectorIndex, config: SemanticConfig): ...
    def retrieve(self, spec: SearchSpecification, k: int) -> SemanticResult: ...
```

- Prompts = `[spec.original_query] + spec.semantic_prompts[:config.max_expansions]`. Combine prompt scores per track with a documented rule (default: weighted max, original query weight ≥ each expansion). Expansions are alternate queries, not requirements.
- Reference tracks (`MORE_LIKE_THIS`) add their **audio** embedding as an extra query vector; negative references subtract via a penalty term in the ranker, not here.
- Returns `[(track_id, raw_cosine, rank)]`, `model_id`, `status: available | unavailable`. Tracks without embeddings are **absent** from the result — never scored 0.
- If the encoder/index is unavailable: `status="unavailable"`, empty results, reason code. The search continues metadata-only and the API reports it.

## 7. Prompt builder (deterministic expansion)

`retrieval/prompt_builder.py` (or Agent A): templates over extracted attributes, e.g. `"{mood} music featuring {instrument}"`, `"{mood} instrumental music with {instrument} melody"`. ≤ 4 prompts; deduplicated; logged with the response for evaluation.

## 8. Tests

- Unit: normalization (zero/NaN vectors raise), cosine correctness, index top-k ordering & `restrict_to`, version mismatch refusal, missing-embedding absence (not zero), prompt-combination rule. All with a `FakeEncoder` (deterministic hashed vectors).
- `@pytest.mark.slow` integration: real checkpoint on 2–3 tiny clips; text "flute" vs "heavy metal drums" ordering sanity on a known flute clip is a *smoke* check, not a quality claim.
