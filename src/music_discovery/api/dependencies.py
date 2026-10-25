"""Composition root: settings → infrastructure → application services (api-contracts §1).

Optional parts degrade instead of failing startup:

- CLAP: the text encoder loads lazily on the first semantic query; a missing checkpoint or
  embedding version leaves search metadata-only (`semantic_reason` says why);
- vector index: needed for original-space neighbors; without it neighbors fall back to labeled
  catalog relationships;
- map: a missing or mismatched projection makes the map endpoints unavailable;
- LLM: only with LLM_PROVIDER configured; otherwise the deterministic paths run.

Routes get services through the `get_*` dependencies; tests replace `app.state.services`
(or use `app.dependency_overrides`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Request

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.agent_b_discovery import DiscoveryAgent
from music_discovery.agents.agent_c_feedback import FeedbackAgent
from music_discovery.agents.feedback_text import FeedbackTextNormalizer
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.agents.llm_query_interpreter import LLMQueryInterpreter
from music_discovery.agents.orchestrator import Orchestrator
from music_discovery.application.capabilities import CapabilityService
from music_discovery.application.feedback_service import FeedbackService
from music_discovery.application.map_service import MapService
from music_discovery.application.results import TrackViewBuilder
from music_discovery.application.search_service import SearchService
from music_discovery.application.track_service import TrackService
from music_discovery.audio.clap_encoder import ClapEncoder
from music_discovery.audio.embedding_store import NpyEmbeddingStore, resolve_version_dir
from music_discovery.descriptions.claim_validator import DescriptionConfig
from music_discovery.descriptions.description_service import DescriptionService
from music_discovery.descriptions.evidence_builder import EvidenceBuilder
from music_discovery.descriptions.llm_phrasing import LLMPhrasing
from music_discovery.domain.errors import MusicDiscoveryError, ProjectionMissing
from music_discovery.domain.models import Track
from music_discovery.infrastructure.clock import SystemClock
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.ids import RandomIdGenerator
from music_discovery.infrastructure.lexical_index import BM25FieldIndex
from music_discovery.infrastructure.llm import build_llm
from music_discovery.infrastructure.repositories import (
    SqlFeedbackRepository,
    SqlRelationshipRepository,
    SqlReleaseRepository,
    SqlSessionRepository,
    SqlTrackAudioRepository,
    SqlTrackRepository,
)
from music_discovery.infrastructure.settings import Settings
from music_discovery.infrastructure.spatial_store import FileProjectionStore
from music_discovery.infrastructure.vector_index import NumpyCosineIndex
from music_discovery.ingestion.catalog_report import iter_tracks
from music_discovery.retrieval.config import RetrievalConfig
from music_discovery.retrieval.hybrid_retriever import HybridRetriever
from music_discovery.retrieval.metadata_retriever import (
    DEFAULT_FIELD_WEIGHTS,
    MetadataRetriever,
    TermExpander,
    TrackFacts,
    metadata_document,
)
from music_discovery.retrieval.relationship_retriever import RelationshipRetriever
from music_discovery.retrieval.semantic_retriever import SemanticRetriever
from music_discovery.spatial.neighbor_service import NeighborService
from music_discovery.spatial.spatial_repository import (
    ProjectionSpatialRepository,
    load_projection,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Services:
    search: SearchService
    feedback: FeedbackService
    tracks: TrackService
    map: MapService
    capabilities: CapabilityService


def build_services(settings: Settings) -> Services:
    database = Database(settings.database_url)
    database.init_schema()
    track_repo = SqlTrackRepository(database)
    releases = SqlReleaseRepository(database)
    audio = SqlTrackAudioRepository(database)
    relationships = SqlRelationshipRepository(database)
    catalog = list(iter_tracks(track_repo))
    clock, ids = SystemClock(), RandomIdGenerator()
    lexicon = load_lexicon()

    store, index, store_reason = _load_embeddings(settings)
    semantic, semantic_reason = None, store_reason
    if index is not None:
        if settings.clap_checkpoint is None or settings.clap_model_version is None:
            semantic_reason = "clap_not_configured"
        elif not settings.clap_checkpoint.exists():
            semantic_reason = "clap_checkpoint_missing"
        else:  # the model itself loads on first use; a failure then degrades per search
            encoder = ClapEncoder(settings.clap_checkpoint, settings.clap_model_version)
            semantic = SemanticRetriever(encoder, index)
    if semantic_reason:
        log.warning("semantic search unavailable: %s", semantic_reason)

    retriever = HybridRetriever(
        RetrievalConfig.load(settings.project_root / "config" / "retrieval.yaml"),
        metadata=_metadata_retriever(catalog, releases, lexicon.expand),
        semantic=semantic,
        tracks=track_repo,
        index=index,
        relationships=RelationshipRetriever(relationships),
    )

    llm = build_llm(settings, cache=False)
    descriptions_config = DescriptionConfig.load()
    phrasing = (
        LLMPhrasing(llm, descriptions_config)
        if llm is not None and settings.llm_descriptions
        else None
    )
    orchestrator = Orchestrator(
        QueryAgent(lexicon, None if llm is None else LLMQueryInterpreter(llm, lexicon)),
        DiscoveryAgent(retriever),
        FeedbackAgent(
            lexicon,
            track_repo,
            EvidenceBuilder(descriptions_config.semantic_bands),
            DescriptionService(descriptions_config, phrasing),
        ),
        SqlSessionRepository(database),
        SqlFeedbackRepository(database),
        clock,
        ids,
        FeedbackTextNormalizer(lexicon, llm),
    )

    catalog_ids = [t.id for t in catalog]

    def load_map() -> ProjectionSpatialRepository:
        if store is None:
            raise ProjectionMissing("no embedding version is loaded, so no map can be validated")
        projections = FileProjectionStore(settings.umap_dir)
        return load_projection(
            projections,
            projections.resolve(settings.active_projection_version),
            embedding_version=store.embedding_version,
            embedded_track_ids=store.track_ids(),
            catalog_track_ids=catalog_ids,
        )

    map_service = MapService.from_loader(track_repo, load_map)
    spatial = map_service.spatial
    views = TrackViewBuilder(track_repo, audio, spatial)
    capabilities = CapabilityService(
        semantic_reason=semantic_reason,
        llm=llm,
        map_service=map_service,
        clock=clock,
    )
    search = SearchService(orchestrator, SqlSessionRepository(database), views, capabilities)
    return Services(
        search=search,
        feedback=FeedbackService(orchestrator, search, ids, clock),
        tracks=TrackService(
            views,
            releases,
            relationships,
            audio,
            NeighborService(index, relationships),
            settings.data_dir,
        ),
        map=map_service,
        capabilities=capabilities,
    )


def _load_embeddings(
    settings: Settings,
) -> tuple[NpyEmbeddingStore | None, NumpyCosineIndex | None, str | None]:
    try:
        directory = resolve_version_dir(settings.embeddings_dir, settings.active_embedding_version)
        store = NpyEmbeddingStore.load(directory, expected_model_id=settings.clap_model_version)
    except (MusicDiscoveryError, OSError, ValueError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        log.warning("embeddings unavailable (%s): %s", code, exc)
        return None, None, "embeddings_unavailable"
    return store, NumpyCosineIndex.from_store(store), None


def _metadata_retriever(
    catalog: list[Track], releases: SqlReleaseRepository, expand: TermExpander
) -> MetadataRetriever:
    album_titles: dict[str, str] = {}
    for release_id in {t.release_id for t in catalog if t.release_id}:
        release = releases.get(release_id)
        if release is not None:
            album_titles[release_id] = release.title
    documents = {t.id: metadata_document(t, album_titles.get(t.release_id or "")) for t in catalog}
    return MetadataRetriever(
        BM25FieldIndex(documents, field_weights=DEFAULT_FIELD_WEIGHTS),
        {t.id: TrackFacts(year=t.year, source=t.provenance.source) for t in catalog},
        expand=expand,
    )


# --- FastAPI dependencies --------------------------------------------------------------


def services(request: Request) -> Services:
    built: Services = request.app.state.services
    return built


def get_search_service(request: Request) -> SearchService:
    return services(request).search


def get_feedback_service(request: Request) -> FeedbackService:
    return services(request).feedback


def get_track_service(request: Request) -> TrackService:
    return services(request).tracks


def get_map_service(request: Request) -> MapService:
    return services(request).map


def get_capability_service(request: Request) -> CapabilityService:
    return services(request).capabilities
