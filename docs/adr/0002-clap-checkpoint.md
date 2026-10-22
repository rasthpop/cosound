# ADR-0002: CLAP checkpoint

- **Status:** Proposed (awaiting review)
- **Date:** 2026-10-21
- **Phase/Task:** P03.T01

## Context

base.md §7.2 and §9 require exactly one explicitly configured, pretrained CLAP checkpoint for both audio and text embeddings, with its version recorded alongside every embedding. The MVP catalog is `fma_small` (ADR-0005): 8,000 × 30 s music clips, encoded on CPU (no GPU on the dev machine or CI; the machine has 12 cores and 13 GB of RAM, most of it used by other applications).

Candidates (checked on the Hugging Face hub on 2026-10-21):

| Option | Package | Weights | License | Notes |
|---|---|---|---|---|
| `laion/larger_clap_music` | `transformers` `ClapModel` | 776 MB | Apache-2.0 | LAION CLAP (HTSAT-base audio + RoBERTa text) trained with music data. **Rejected: text embeddings collapse (see below)** |
| **`laion/larger_clap_music_and_speech`** | `transformers` | 776 MB | Apache-2.0 | same architecture, trained on music + speech; also helps vocal queries |
| `laion/clap-htsat-unfused` | `transformers` | 615 MB | Apache-2.0 | general audio (630k-audioset), not music-specific |
| `music_audioset_epoch_15_esc_90.14.pt` | `laion_clap` | 2,352 MB | CC0 | same model family, but the file includes optimizer state, and `laion-clap` 1.1.7 requires `numpy<2` plus wandb, webdataset, h5py, … |

## Decision

Use **`laion/larger_clap_music_and_speech`** through Hugging Face `transformers` (`ClapModel` + `ClapProcessor`), pinned to revision `195c3a3e68faebb3e2088b9a79e79b43ddbda76b`.

| Setting | Value |
|---|---|
| `CLAP_MODEL_VERSION` | `laion/larger_clap_music_and_speech@195c3a3e68faebb3e2088b9a79e79b43ddbda76b` |
| `CLAP_CHECKPOINT` | local snapshot directory, default `data/models/larger_clap_music_and_speech` (git-ignored) |
| Weights SHA-256 (`pytorch_model.bin`) | `b73c5e596fda5b29b522a1ab3f0842977fe2b147bf8b78c2ec5f7ae6267038a1` |
| Audio input | mono float32 at 48 kHz (the processor's sampling rate); clips are resampled with `scipy.signal.resample_poly` |
| Windowing | the processor's default `rand_trunc` randomly crops audio longer than 10 s, which would make embeddings non-reproducible. The encoder therefore splits each clip into non-overlapping 10 s windows (at most 3 for a 30 s clip; a final window shorter than 3 s is dropped unless it is the only one). Each window is exactly the model's input length or shorter, so no random crop happens. The windows are embedded, mean-pooled and L2-normalized. |
| Embedding | projected 512-d `get_audio_features` / `get_text_features` output (`pooler_output`), L2-normalized and stored as float32 |
| Runtime | `torch` CPU build (`pytorch-cpu` uv index), `torch.inference_mode()`, `model.eval()` |

`scripts/fetch_clap_model.py` downloads that exact revision and verifies the weights' SHA-256. The model is never downloaded implicitly at runtime.

### Why not `laion/larger_clap_music` (the first choice)

On 2026-10-21 the pinned `laion/larger_clap_music` checkpoint (revision `a0b4534…`) loaded without missing or unexpected keys, but produced **collapsed text embeddings**: four very different prompts ("a pure sine tone", "white noise", "a calm flute melody", "aggressive heavy metal with drums") had pairwise cosine ≥ 0.999, and every audio-text similarity was about 0.01. The behavior was identical under `transformers` 5.20.2 and 4.46.3 and with eager attention, so it comes from the checkpoint conversion, not from our code. With the same probe, `larger_clap_music_and_speech` and `clap-htsat-unfused` both behave sensibly: each probe sound matches its own description best (sine tone ↔ "a pure sine tone": 0.60 and 0.67), and the text embeddings are distinct (pairwise cosine ≤ 0.6). The probe script is in the P03 PR description; `tests/integration/audio/test_clap_encoder.py` keeps a slow regression test for text-embedding collapse.

## Consequences

- One dependency stack (`torch` + `transformers`) instead of `laion-clap`'s pinned, older one. numpy 2 / pandas 3 stay compatible.
- Embeddings are tied to the revision. Changing the revision, the preprocessing, or the `transformers` version that defines the feature extractor creates a new `embedding_version`; the store refuses to mix them.
- The model needs about 1 GB of RAM at inference. Building embeddings for the 8,000 clips takes tens of minutes on CPU; it runs offline (`scripts/build_embeddings.py`), never per request.
- `laion/clap-htsat-unfused` (general audio) is the documented fallback if music queries evaluate poorly (P05/P10). Switching is a configuration change plus a rebuild.

## Reversible by

Set `CLAP_MODEL_VERSION` / `CLAP_CHECKPOINT` to another `transformers` CLAP checkpoint and rebuild embeddings, index and map. A `laion_clap`-based encoder would be a second implementation of the same `AudioEncoder`/`TextEncoder` protocols in `audio/`.
