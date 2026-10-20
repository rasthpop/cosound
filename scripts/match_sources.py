"""Match FMA tracks to Discogs tracks conservatively and store every decision.

uv run python scripts/match_sources.py
"""

from __future__ import annotations

import sys
from collections import Counter

from music_discovery.domain.enums import DataSource
from music_discovery.domain.models import Track
from music_discovery.infrastructure.clock import SystemClock
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlMatchRepository,
    SqlReleaseRepository,
    SqlTrackRepository,
)
from music_discovery.infrastructure.settings import get_settings
from music_discovery.ingestion.matcher import SourceMatcher


def main() -> int:
    database = Database(get_settings().database_url)
    database.init_schema()
    tracks_repo = SqlTrackRepository(database)
    releases_repo = SqlReleaseRepository(database)
    tracks: list[Track] = []
    after: str | None = None
    while page := tracks_repo.list_page(limit=1000, after=after):
        tracks.extend(page)
        after = page[-1].id
    discogs = [t for t in tracks if t.provenance.source is DataSource.DISCOGS]
    fma = [t for t in tracks if t.provenance.source is DataSource.FMA]
    release_ids = {t.release_id for t in tracks if t.release_id}
    titles = {rid: r.title for rid in release_ids if (r := releases_repo.get(rid)) is not None}
    matcher = SourceMatcher(discogs, release_titles=titles)
    clock = SystemClock()
    outcome: Counter[str] = Counter()
    matches = SqlMatchRepository(database)
    with database.transaction():
        for track in fma:
            decision = matcher.match(track, decided_at=clock.now())
            if decision is None:
                outcome["no_candidates"] += 1
                continue
            matches.upsert(decision)
            outcome[str(decision.status)] += 1
    print(
        f"{len(fma)} FMA tracks vs {len(discogs)} Discogs tracks: {dict(sorted(outcome.items()))}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
