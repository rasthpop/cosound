"""Recompute the catalog relationship graph from the local catalog.

uv run python scripts/build_relationships.py
"""

from __future__ import annotations

import sys
from collections import Counter

from music_discovery.domain.models import Track
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlRelationshipRepository,
    SqlTrackRepository,
)
from music_discovery.infrastructure.settings import get_settings
from music_discovery.ingestion.relationships import derive_relationships


def main() -> int:
    database = Database(get_settings().database_url)
    database.init_schema()
    tracks_repo = SqlTrackRepository(database)
    tracks: list[Track] = []
    after: str | None = None
    while page := tracks_repo.list_page(limit=1000, after=after):
        tracks.extend(page)
        after = page[-1].id
    edges = derive_relationships(tracks)
    with database.transaction():
        SqlRelationshipRepository(database).replace_all(edges)
    counts = Counter(str(e.relationship_type) for e in edges)
    print(f"{len(tracks)} tracks, {len(edges)} edges: {dict(sorted(counts.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
