"""Summarize the local catalog, or look tracks up by title/artist. Never uses the network.

uv run python scripts/catalog_stats.py
uv run python scripts/catalog_stats.py --lookup "flute"
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlMatchRepository,
    SqlTrackAudioRepository,
    SqlTrackRepository,
)
from music_discovery.infrastructure.settings import get_settings
from music_discovery.ingestion.catalog_report import lookup, summarize


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--lookup")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    database = Database(get_settings().database_url)
    database.init_schema()
    tracks = SqlTrackRepository(database)
    if args.lookup:
        for track in lookup(tracks, args.lookup, limit=args.limit):
            artists = ", ".join(a.name for a in track.artists) or "-"
            print(f"{track.id}  {track.title} — {artists}  [{track.provenance.source}]")
        return 0
    summary = summarize(tracks, SqlTrackAudioRepository(database), SqlMatchRepository(database))
    print(json.dumps(asdict(summary), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
