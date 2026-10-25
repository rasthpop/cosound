"""In-memory fakes implementing domain protocols, shared by unit tests.

Each protocol in `music_discovery.domain.protocols` has a fake here. `make type` checks them
against the protocols with mypy (see tests/unit/fakes/test_fakes_conform.py).
"""

from tests.fakes.adapters import (
    FakeAudioProbe,
    FakeLexicalIndex,
    FakeStructuredLLM,
    InMemoryProjectionStore,
    InMemorySpatialRepository,
)
from tests.fakes.clock import FrozenClock
from tests.fakes.ids import SequentialIdGenerator
from tests.fakes.repositories import (
    InMemoryArtistRepository,
    InMemoryFeedbackRepository,
    InMemoryImportRunRepository,
    InMemoryLabelRepository,
    InMemoryMatchRepository,
    InMemoryRelationshipRepository,
    InMemoryReleaseRepository,
    InMemorySessionRepository,
    InMemoryTrackAudioRepository,
    InMemoryTrackRepository,
    InMemoryUnitOfWork,
)
from tests.fakes.vectors import (
    BruteForceVectorIndex,
    FakeEncoder,
    InMemoryEmbeddingStore,
    hashed_unit_vector,
)

__all__ = [
    "BruteForceVectorIndex",
    "FakeAudioProbe",
    "FakeEncoder",
    "FakeLexicalIndex",
    "FakeStructuredLLM",
    "FrozenClock",
    "InMemoryArtistRepository",
    "InMemoryEmbeddingStore",
    "InMemoryFeedbackRepository",
    "InMemoryImportRunRepository",
    "InMemoryLabelRepository",
    "InMemoryMatchRepository",
    "InMemoryProjectionStore",
    "InMemoryRelationshipRepository",
    "InMemoryReleaseRepository",
    "InMemorySessionRepository",
    "InMemorySpatialRepository",
    "InMemoryTrackAudioRepository",
    "InMemoryTrackRepository",
    "InMemoryUnitOfWork",
    "SequentialIdGenerator",
    "hashed_unit_vector",
]
