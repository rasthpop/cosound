"""In-memory fakes implementing domain protocols, shared by unit tests.

Each protocol introduced in `music_discovery.domain.protocols` gets its fake here in the same task.
"""

from tests.fakes.clock import FrozenClock
from tests.fakes.ids import SequentialIdGenerator

__all__ = ["FrozenClock", "SequentialIdGenerator"]
