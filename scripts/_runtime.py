"""Composition helpers shared by the scripts (the API gets its own root in P08).

Builds the hybrid engine from local artifacts: the SQLite catalog, the active embedding
version, the CLAP checkpoint and config/retrieval.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass

from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.audio.clap_encoder import ClapEncoder
from music_discovery.audio.embedding_store import NpyEmbeddingStore, resolve_version_dir
from music_discovery.domain.models import Track
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.lexical_index import BM25FieldIndex
from music_discovery.infrastructure.repositories import (
    SqlRelationshipRepository,
    SqlReleaseRepository,
    SqlTrackRepository,
)
from music_discovery.infrastructure.settings import Settings
from music_discovery.infrastructure.vector_index import NumpyCosineIndex
from music_discovery.ingestion.catalog_report import iter_tracks
from music_discovery.retrieval.config import RetrievalConfig
from music_discovery.retrieval.hybrid_retriever import HybridRetriever
from music_discovery.retrieval.metadata_retriever import (
    DEFAULT_FIELD_WEIGHTS,
    MetadataRetriever,
    TrackFacts,
    metadata_document,
)
from music_discovery.retrieval.relationship_retriever import RelationshipRetriever
from music_discovery.retrieval.semantic_retriever import SemanticRetriever


@dataclass
class Runtime:
    retriever: HybridRetriever
    tracks: dict[str, Track]
    embedding_version: str | None


def build_runtime(settings: Settings, *, semantic: bool = True) -> Runtime:
    database = Database(settings.database_url)
    track_repo = SqlTrackRepository(database)
    releases = SqlReleaseRepository(database)
    tracks = {t.id: t for t in iter_tracks(track_repo)}
    album_titles: dict[str, str] = {}
    for release_id in {t.release_id for t in tracks.values() if t.release_id}:
        release = releases.get(release_id)
        if release is not None:
            album_titles[release_id] = release.title
    documents = {
        t.id: metadata_document(t, album_titles.get(t.release_id or "")) for t in tracks.values()
    }
    metadata = MetadataRetriever(
        BM25FieldIndex(documents, field_weights=DEFAULT_FIELD_WEIGHTS),
        {t.id: TrackFacts(year=t.year, source=t.provenance.source) for t in tracks.values()},
        expand=load_lexicon().expand,
    )

    index = None
    semantic_retriever = None
    version = None
    if (
        semantic
        and settings.clap_checkpoint is not None
        and settings.clap_model_version is not None
    ):
        directory = resolve_version_dir(settings.embeddings_dir, settings.active_embedding_version)
        store = NpyEmbeddingStore.load(directory, expected_model_id=settings.clap_model_version)
        index = NumpyCosineIndex.from_store(store)
        version = store.embedding_version
        semantic_retriever = SemanticRetriever(
            ClapEncoder(settings.clap_checkpoint, settings.clap_model_version), index
        )

    config = RetrievalConfig.load(settings.project_root / "config" / "retrieval.yaml")
    retriever = HybridRetriever(
        config,
        metadata=metadata,
        semantic=semantic_retriever,
        tracks=track_repo,
        index=index,
        relationships=RelationshipRetriever(SqlRelationshipRepository(database)),
    )
    return Runtime(retriever=retriever, tracks=tracks, embedding_version=version)
