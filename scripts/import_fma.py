"""Import FMA tracks into the local catalog, validating any audio that is present.

    uv run python scripts/import_fma.py                  # tracks in the evaluation manifest
    uv run python scripts/import_fma.py --subset small   # all fma_small metadata (8,000 tracks)
    uv run python scripts/import_fma.py --subset small --limit 500

Audio is looked for under DATA_DIR/raw/fma/fma_small/<000>/<000123>.mp3. Tracks without a
decodable file are imported as metadata-only records.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

from music_discovery.audio.audio_probe import SoundfileProbe
from music_discovery.domain.ids import IdPrefix, random_id
from music_discovery.infrastructure.clock import SystemClock
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import (
    SqlArtistRepository,
    SqlImportRunRepository,
    SqlReleaseRepository,
    SqlTrackAudioRepository,
    SqlTrackRepository,
)
from music_discovery.infrastructure.settings import get_settings
from music_discovery.ingestion.fma_loader import FmaImporter, FmaWriters, load_genres, load_tracks


class RandomIds:
    def new(self, prefix: IdPrefix) -> str:
        return random_id(prefix)


def manifest_ids(path: Path) -> list[int]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(line for line in handle if not line.startswith("#"))
        return [int(row["fma_track_id"]) for row in rows]


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--manifest", type=Path, default=settings.evaluation_dir / "fma_20_manifest.csv"
    )
    parser.add_argument("--subset", choices=["small", "medium", "large"])
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--metadata-dir", type=Path, default=settings.raw_dir / "fma" / "fma_metadata"
    )
    parser.add_argument("--audio-dir", type=Path, default=settings.raw_dir / "fma" / "fma_small")
    args = parser.parse_args()

    records = load_tracks(args.metadata_dir, subset=args.subset or "large")
    if args.subset is None:
        wanted = set(manifest_ids(args.manifest))
        records = [r for r in records if r.fma_track_id in wanted]
    if args.limit is not None:
        records = records[: args.limit]

    database = Database(settings.database_url)
    database.init_schema()
    importer = FmaImporter(
        FmaWriters(
            tracks=SqlTrackRepository(database),
            releases=SqlReleaseRepository(database),
            artists=SqlArtistRepository(database),
            audio=SqlTrackAudioRepository(database),
            runs=SqlImportRunRepository(database),
            uow=database,
        ),
        SoundfileProbe(),
        data_dir=settings.data_dir,
        clock=SystemClock(),
        ids=RandomIds(),
    )
    report = importer.run(records, audio_dir=args.audio_dir, genres=load_genres(args.metadata_dir))
    summary = asdict(report) | {"failures": [f.model_dump() for f in report.failures[:50]]}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
