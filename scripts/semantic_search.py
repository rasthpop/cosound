"""Text-to-audio search over the local corpus (P03 smoke check; no ranking or agents yet).

    uv run python scripts/semantic_search.py "something chill with a flute" -k 5
    uv run python scripts/semantic_search.py "dark electronic" \
        --prompt "dark heavy electronic music featuring bass"

Scores are raw CLAP cosine similarities: a ranking signal, not a probability.
"""

from __future__ import annotations

import argparse
import sys

from music_discovery.audio.clap_encoder import ClapEncoder
from music_discovery.audio.embedding_store import NpyEmbeddingStore, resolve_version_dir
from music_discovery.domain.schemas import SearchSpecification
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import SqlTrackRepository
from music_discovery.infrastructure.settings import get_settings
from music_discovery.infrastructure.vector_index import NumpyCosineIndex
from music_discovery.retrieval.semantic_retriever import SemanticRetriever


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("query")
    parser.add_argument("-k", type=int, default=10)
    parser.add_argument("--prompt", action="append", default=[], help="extra expansion prompt")
    args = parser.parse_args()

    settings = get_settings()
    if settings.clap_checkpoint is None or settings.clap_model_version is None:
        print("CLAP_CHECKPOINT and CLAP_MODEL_VERSION must be set (ADR-0002).", file=sys.stderr)
        return 2
    directory = resolve_version_dir(settings.embeddings_dir, settings.active_embedding_version)
    store = NpyEmbeddingStore.load(directory, expected_model_id=settings.clap_model_version)
    retriever = SemanticRetriever(
        ClapEncoder(settings.clap_checkpoint, settings.clap_model_version),
        NumpyCosineIndex.from_store(store),
    )
    spec = SearchSpecification(original_query=args.query, semantic_prompts=args.prompt[:4])
    result = retriever.retrieve(spec, k=args.k)
    if result.status != "available":
        print(f"semantic retrieval unavailable: {result.reason}", file=sys.stderr)
        return 1

    tracks = {
        t.id: t
        for t in SqlTrackRepository(Database(settings.database_url)).get_many(
            [h.track_id for h in result.hits]
        )
    }
    size = len(store.track_ids())
    print(f"model {result.model_id} | embeddings {store.embedding_version} ({size} tracks)")
    for hit in result.hits:
        track = tracks.get(hit.track_id)
        title = track.title if track else "?"
        artist = ", ".join(a.name for a in track.artists) if track else "?"
        genre = track.genres[0] if track and track.genres else "-"
        via = (
            hit.best_query.kind
            if hit.best_query.kind != "expansion"
            else f"expansion: {hit.best_query.text}"
        )
        print(f"{hit.rank:>3}  {hit.raw_cosine:6.3f}  {title} — {artist}  [{genre}]  ({via})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
