"""Bounded Discogs import. See docs/data-sources.md#import.

uv run python scripts/import_discogs.py                    # fetch missing releases, then import
uv run python scripts/import_discogs.py --from-cache-only  # no network; normalize from cache
uv run python scripts/import_discogs.py --dry-run          # show the plan, write nothing
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

import httpx

from music_discovery.domain.ids import IdPrefix, random_id
from music_discovery.infrastructure.clock import SystemClock
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlArtistRepository,
    SqlImportRunRepository,
    SqlLabelRepository,
    SqlReleaseRepository,
    SqlTrackRepository,
)
from music_discovery.infrastructure.settings import get_settings
from music_discovery.ingestion.catalog_importer import CatalogImporter, CatalogWriters
from music_discovery.ingestion.discogs_client import DiscogsClient
from music_discovery.ingestion.raw_cache import RawCache
from music_discovery.ingestion.selection import Selection


class RandomIds:
    def new(self, prefix: IdPrefix) -> str:
        return random_id(prefix)


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--selection",
        type=Path,
        default=settings.project_root / "config" / "discogs_selection.yaml",
    )
    parser.add_argument("--from-cache-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    selection = Selection.load(args.selection)
    database = Database(settings.database_url)
    database.init_schema()
    clock = SystemClock()
    token = settings.discogs_token.get_secret_value() if settings.discogs_token else None
    offline = args.from_cache_only or args.dry_run
    with httpx.Client() as http:
        source = (
            None
            if offline
            else DiscogsClient(
                http, user_agent=settings.discogs_user_agent, token=token, clock=clock
            )
        )
        importer = CatalogImporter(
            source,
            RawCache(settings.raw_dir / "discogs"),
            CatalogWriters(
                tracks=SqlTrackRepository(database),
                releases=SqlReleaseRepository(database),
                artists=SqlArtistRepository(database),
                labels=SqlLabelRepository(database),
                runs=SqlImportRunRepository(database),
                uow=database,
            ),
            clock=clock,
            ids=RandomIds(),
        )
        report = importer.run(selection, from_cache_only=args.from_cache_only, dry_run=args.dry_run)
    print(
        json.dumps(asdict(report) | {"errors": [e.model_dump() for e in report.errors]}, indent=2)
    )
    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
