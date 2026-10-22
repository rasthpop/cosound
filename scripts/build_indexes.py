"""Build and validate the vector index for the active embedding version.

    uv run python scripts/build_indexes.py

Uses ACTIVE_EMBEDDING_VERSION, or the newest version under data/embeddings/. Writes
data/indexes/<embedding_version>.json with counts, a self-retrieval check (ties with
identical audio count as found) and the groups of duplicate audio found in the catalog.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

import numpy as np

from music_discovery.audio.embedding_store import NpyEmbeddingStore, resolve_version_dir
from music_discovery.domain.protocols import Matrix
from music_discovery.infrastructure.settings import get_settings
from music_discovery.infrastructure.vector_index import NumpyCosineIndex

TIE_TOLERANCE = 1e-5
DUPLICATE_COSINE = 0.9999
"""Tracks this similar have (near-)identical audio: FMA contains some double uploads."""


def duplicate_groups(ids: list[str], matrix: Matrix, block: int = 1024) -> list[list[str]]:
    """Connected groups of tracks whose embeddings are practically identical."""
    parent = list(range(len(ids)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for start in range(0, len(ids), block):
        sims = matrix[start : start + block] @ matrix.T
        rows, cols = np.nonzero(sims >= DUPLICATE_COSINE)
        for r, c in zip(rows + start, cols, strict=True):
            if r < c:
                parent[find(int(r))] = find(int(c))
    groups: dict[int, list[str]] = {}
    for i, track_id in enumerate(ids):
        groups.setdefault(find(i), []).append(track_id)
    return sorted(sorted(g) for g in groups.values() if len(g) > 1)


def main() -> int:
    settings = get_settings()
    directory = resolve_version_dir(settings.embeddings_dir, settings.active_embedding_version)
    store = NpyEmbeddingStore.load(directory, expected_model_id=settings.clap_model_version)
    index = NumpyCosineIndex.from_store(store)
    ids, matrix = store.matrix()
    misses = []
    for track_id, vector in zip(ids, matrix, strict=True):
        top_id, top_score = index.search(vector, 1)[0]
        own = float(vector @ vector)
        # a tie with another track (identical audio) still counts as finding itself
        if top_id != track_id and own < top_score - TIE_TOLERANCE:
            misses.append(track_id)
    duplicates = duplicate_groups(ids, matrix)
    meta = {
        "embedding_version": store.embedding_version,
        "model_id": store.model_id,
        "kind": "numpy_exact_cosine",
        "n": index.size,
        "dim": int(matrix.shape[1]) if matrix.size else None,
        "self_retrieval_misses": misses[:20],
        "self_retrieval_ok": not misses,
        "duplicate_audio_threshold": DUPLICATE_COSINE,
        "duplicate_audio_groups": duplicates,
        "built_at": datetime.now(UTC).isoformat(),
    }
    settings.indexes_dir.mkdir(parents=True, exist_ok=True)
    out = settings.indexes_dir / f"{store.embedding_version}.json"
    out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0 if not misses else 1


if __name__ == "__main__":
    sys.exit(main())
