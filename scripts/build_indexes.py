"""Build and validate the vector index for the active embedding version.

    uv run python scripts/build_indexes.py

Uses ACTIVE_EMBEDDING_VERSION, or the newest version under data/embeddings/. Writes
data/indexes/<embedding_version>.json with counts and a self-retrieval check.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from music_discovery.audio.embedding_store import NpyEmbeddingStore, resolve_version_dir
from music_discovery.infrastructure.settings import get_settings
from music_discovery.infrastructure.vector_index import NumpyCosineIndex


def main() -> int:
    settings = get_settings()
    directory = resolve_version_dir(settings.embeddings_dir, settings.active_embedding_version)
    store = NpyEmbeddingStore.load(directory, expected_model_id=settings.clap_model_version)
    index = NumpyCosineIndex.from_store(store)
    ids, matrix = store.matrix()
    misses = [
        track_id
        for track_id, vector in zip(ids, matrix, strict=True)
        if index.search(vector, 1)[0][0] != track_id
    ]
    meta = {
        "embedding_version": store.embedding_version,
        "model_id": store.model_id,
        "kind": "numpy_exact_cosine",
        "n": index.size,
        "dim": int(matrix.shape[1]) if matrix.size else None,
        "self_retrieval_misses": misses[:20],
        "self_retrieval_ok": not misses,
        "built_at": datetime.now(UTC).isoformat(),
    }
    settings.indexes_dir.mkdir(parents=True, exist_ok=True)
    out = settings.indexes_dir / f"{store.embedding_version}.json"
    out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0 if not misses else 1


if __name__ == "__main__":
    sys.exit(main())
