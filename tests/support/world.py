"""A small, fully wired application over in-memory fakes, for service and API tests.

Real agents, retrievers and descriptions; fake repositories, a hashed-vector encoder and an
in-memory projection. Each degraded mode is a constructor switch.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.agent_b_discovery import DiscoveryAgent
from music_discovery.agents.agent_c_feedback import FeedbackAgent
from music_discovery.agents.feedback_text import FeedbackTextNormalizer
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.agents.llm_query_interpreter import LLMQueryInterpreter
from music_discovery.agents.orchestrator import Orchestrator
from music_discovery.api.dependencies import Services
from music_discovery.application.capabilities import CapabilityService
from music_discovery.application.feedback_service import FeedbackService
from music_discovery.application.map_service import MapService
from music_discovery.application.results import TrackViewBuilder
from music_discovery.application.search_service import SearchService
from music_discovery.application.track_service import TrackService
from music_discovery.descriptions.claim_validator import DescriptionConfig
from music_discovery.descriptions.description_service import DescriptionService
from music_discovery.descriptions.evidence_builder import EvidenceBuilder
from music_discovery.domain.enums import DataSource, RelationshipType
from music_discovery.domain.errors import ModelLoadError, ProjectionMissing
from music_discovery.domain.models import (
    ArtistReference,
    Provenance,
    Release,
    Track,
    TrackAudio,
    TrackRelationship,
)
from music_discovery.domain.schemas import ProjectionArtifact, ProjectionMeta
from music_discovery.infrastructure.lexical_index import BM25FieldIndex
from music_discovery.infrastructure.vector_index import NumpyCosineIndex
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
from music_discovery.spatial.neighbor_service import NeighborService
from music_discovery.spatial.spatial_repository import ProjectionSpatialRepository
from tests.fakes import (
    FakeEncoder,
    FakeStructuredLLM,
    FrozenClock,
    InMemoryFeedbackRepository,
    InMemoryRelationshipRepository,
    InMemoryReleaseRepository,
    InMemorySessionRepository,
    InMemoryTrackAudioRepository,
    InMemoryTrackRepository,
    SequentialIdGenerator,
    hashed_unit_vector,
)

REPO = Path(__file__).parents[2]
DIM = 32
QUERY = "calm flute melody"
FMA = Provenance(source=DataSource.FMA)
LEXICON = load_lexicon()
DESCRIPTIONS = DescriptionConfig.load()
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def text_vec(text: str) -> np.ndarray:
    return hashed_unit_vector(f"text:{text}", DIM)


def mix(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    v = (1 - t) * a + t * b
    return (v / np.linalg.norm(v)).astype(np.float32)


def track(
    tid: str,
    title: str,
    genres: list[str],
    *,
    artist: str | None = None,
    release_id: str | None = None,
    source_url: str | None = None,
    embedded: bool = True,
) -> Track:
    return Track(
        id=tid,
        title=title,
        genres=genres,
        artists=[ArtistReference(artist_id=f"art_{artist or tid}", name=f"Artist {artist or tid}")],
        release_id=release_id,
        source_url=source_url,
        audio_source=DataSource.FMA if embedded else None,
        audio_path=f"raw/fma/{tid}.mp3" if embedded else None,
        audio_embedding_id="ev-test" if embedded else None,
        provenance=FMA,
    )


NIGHT = hashed_unit_vector("night", DIM)
CATALOG = [
    track("trk_sound", "Morning", ["Folk"], source_url="https://freemusicarchive.org/t/1"),
    track("trk_both", "Flute Garden", ["Folk", "Instrumental"], release_id="rel_garden"),
    track("trk_title", "Flute Riot", ["Punk"]),
    track("trk_tape", "Calm Flute Tape", ["Folk"], embedded=False),
    track("trk_night", "Night Train", ["Electronic"], artist="nocturne"),
    track("trk_bus", "Night Bus", ["Electronic"], artist="nocturne"),
    *[track(f"trk_fill{i}", f"Filler {i}", ["Rock"]) for i in range(6)],
]
EMBEDDED = [t.id for t in CATALOG if t.audio_embedding_id is not None]
VECTORS = {
    "trk_sound": text_vec(QUERY),
    "trk_both": mix(text_vec(QUERY), hashed_unit_vector("noise", DIM), 0.35),
    "trk_title": hashed_unit_vector("noise", DIM),
    "trk_night": NIGHT,
    "trk_bus": mix(NIGHT, hashed_unit_vector("bus", DIM), 0.15),
    **{f"trk_fill{i}": hashed_unit_vector(f"filler{i}", DIM) for i in range(6)},
}
AUDIO_BYTES = b"ID3" + bytes(range(256)) * 8
"""Stand-in clip content (2 KB); the API only streams it, nothing decodes it."""


class FailingEncoder(FakeEncoder):
    """A CLAP encoder whose model cannot be loaded (corrupt checkpoint, OOM, ...)."""

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        raise ModelLoadError("CLAP checkpoint could not be loaded")


@dataclass
class LLMStatus:
    status: str = "available"


def projection() -> ProjectionSpatialRepository:
    ids = sorted(EMBEDDED)
    coords = [
        (round(-1.0 + 2 * i / (len(ids) - 1), 6), 0.5 if i % 2 else -0.5) for i in range(len(ids))
    ]
    meta = ProjectionMeta(
        projection_version="umap-test",
        embedding_version="ev-test",
        model_id="fake-clap-v1",
        umap_requested={"n_neighbors": 15},
        umap_effective={"n_neighbors": 10},
        random_state=42,
        package_versions={},
        created_at=NOW,
        n_points=len(ids),
        excluded_tracks=1,
        coordinates_sha256="0" * 64,
    )
    return ProjectionSpatialRepository(
        ProjectionArtifact(meta=meta, track_ids=ids, coordinates=coords)
    )


class World:
    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        semantic: bool = True,
        projection_available: bool = True,
        llm_responses: Sequence[BaseModel | str] | None = None,
        llm_status: str = "available",
        encoder_fails: bool = False,
    ) -> None:
        self.data_dir = data_dir or Path("/nonexistent-data-dir")
        self.clock = FrozenClock(NOW)
        self.ids = SequentialIdGenerator()
        self.tracks = InMemoryTrackRepository()
        for t in CATALOG:
            self.tracks.upsert(t)
        self.releases = InMemoryReleaseRepository()
        self.releases.upsert(
            Release(id="rel_garden", title="Garden Sessions", year=2011, provenance=FMA)
        )
        self.audio = InMemoryTrackAudioRepository()
        for track_id in EMBEDDED:
            file_path = f"raw/fma/{track_id}.mp3"
            self.audio.upsert(
                TrackAudio(
                    track_id=track_id,
                    source=DataSource.FMA,
                    file_path=file_path,
                    duration_seconds=30.0,
                    license="Attribution 4.0 International",
                )
            )
            if data_dir is not None:
                path = data_dir / file_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(AUDIO_BYTES)
        self.relationships = InMemoryRelationshipRepository()
        for a, b in (("trk_night", "trk_bus"), ("trk_bus", "trk_night")):
            self.relationships.upsert(
                TrackRelationship(
                    source_track_id=a,
                    target_track_id=b,
                    relationship_type=RelationshipType.SAME_ARTIST,
                    evidence_source=DataSource.FMA,
                )
            )

        encoder = FailingEncoder(dim=DIM) if encoder_fails else FakeEncoder(dim=DIM)
        self.index = NumpyCosineIndex(
            list(VECTORS), np.stack(list(VECTORS.values())), model_id="fake-clap-v1"
        )
        docs = {t.id: metadata_document(t, None) for t in CATALOG}
        metadata = MetadataRetriever(
            BM25FieldIndex(docs, field_weights=DEFAULT_FIELD_WEIGHTS),
            {t.id: TrackFacts(year=t.year, source=t.provenance.source) for t in CATALOG},
            expand=LEXICON.expand,
        )
        retriever = HybridRetriever(
            RetrievalConfig.load(REPO / "config" / "retrieval.yaml"),
            metadata=metadata,
            semantic=SemanticRetriever(encoder, self.index) if semantic else None,
            tracks=self.tracks,
            index=self.index if semantic else None,
            relationships=RelationshipRetriever(self.relationships),
        )

        self.llm = None if llm_responses is None else FakeStructuredLLM(llm_responses)
        self.llm_status = None if self.llm is None else LLMStatus(llm_status)
        interpreter = None if self.llm is None else LLMQueryInterpreter(self.llm, LEXICON)
        self.sessions = InMemorySessionRepository()
        self.events = InMemoryFeedbackRepository()
        self.orchestrator = Orchestrator(
            QueryAgent(LEXICON, interpreter),
            DiscoveryAgent(retriever),
            FeedbackAgent(
                LEXICON,
                self.tracks,
                EvidenceBuilder(DESCRIPTIONS.semantic_bands),
                DescriptionService(DESCRIPTIONS),
            ),
            self.sessions,
            self.events,
            self.clock,
            self.ids,
            FeedbackTextNormalizer(LEXICON),
        )

        def load() -> ProjectionSpatialRepository:
            if not projection_available:
                raise ProjectionMissing("no projection in this test world")
            return projection()

        self.map = MapService.from_loader(self.tracks, load)
        spatial = None if not self.map.available else projection()
        self.views = TrackViewBuilder(self.tracks, self.audio, spatial)
        self.capabilities = CapabilityService(
            semantic_reason=None if semantic else "clap_checkpoint_missing",
            llm=self.llm_status,
            map_service=self.map,
            clock=self.clock,
        )
        self.search = SearchService(self.orchestrator, self.sessions, self.views, self.capabilities)
        self.feedback = FeedbackService(self.orchestrator, self.search, self.ids, self.clock)
        self.track_service = TrackService(
            self.views,
            self.releases,
            self.relationships,
            self.audio,
            NeighborService(self.index if semantic else None, self.relationships),
            self.data_dir,
        )

    def services(self) -> Services:
        return Services(
            search=self.search,
            feedback=self.feedback,
            tracks=self.track_service,
            map=self.map,
            capabilities=self.capabilities,
        )
