"""Random session/query/event ids for composition roots. Tests use `SequentialIdGenerator`."""

from __future__ import annotations

from music_discovery.domain.ids import IdPrefix, random_id


class RandomIdGenerator:
    def new(self, prefix: IdPrefix) -> str:
        return random_id(prefix)
