"""Build CLAP audio embeddings for the catalog (offline; base.md §9.1).

    uv run python scripts/build_embeddings.py                    # every track with validated audio
    uv run python scripts/build_embeddings.py --source manifest  # the 20 evaluation tracks only
    uv run python scripts/build_embeddings.py --limit 50         # quick smoke run

Interrupted runs resume from data/embeddings/cache/<version>/. Prints the embedding version;
set ACTIVE_EMBEDDING_VERSION to it to make it the one search uses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

from music_discovery.audio.clap_encoder import ClapEncoder
from music_discovery.audio.embedding_builder import EmbeddingBuilder
from music_discovery.infrastructure.clock import SystemClock
from music_discovery.infrastructure.database import Database
from music_discovery.infrastructure.repositories import SqlTrackAudioRepository, SqlTrackRepository
from music_discovery.infrastructure.settings import get_settings
from music_discovery.ingestion.fma_loader import fma_track_id
from music_discovery.ingestion.fma_manifest import read_manifest


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", choices=["catalog", "manifest"], default="catalog")
    parser.add_argument(
        "--manifest", type=Path, default=settings.evaluation_dir / "fma_20_manifest.csv"
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--threads", type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if settings.clap_checkpoint is None or settings.clap_model_version is None:
        print("CLAP_CHECKPOINT and CLAP_MODEL_VERSION must be set (ADR-0002).", file=sys.stderr)
        return 2
    database = Database(settings.database_url)
    database.init_schema()
    audio, tracks = SqlTrackAudioRepository(database), SqlTrackRepository(database)

    manifest_sha = None
    track_ids: list[str] | None = None
    if args.source == "manifest":
        manifest_sha = sha256_of(args.manifest)
        track_ids = [fma_track_id(int(r["fma_track_id"])) for r in read_manifest(args.manifest)]
    if args.limit is not None:
        pool = track_ids if track_ids is not None else [a.track_id for a in audio.list_all()]
        track_ids = sorted(pool)[: args.limit]

    started = time.monotonic()

    def progress(done: int, total: int) -> None:
        if done % 100 == 0 or done == total:
            rate = done / max(time.monotonic() - started, 1e-6)
            eta_min = (total - done) / rate / 60 if rate else float("nan")
            logging.info(
                "embedded %d/%d (%.1f files/s, ~%.0f min left)", done, total, rate, eta_min
            )

    weights = settings.clap_checkpoint / "pytorch_model.bin"
    builder = EmbeddingBuilder(
        ClapEncoder(
            settings.clap_checkpoint, settings.clap_model_version, num_threads=args.threads
        ),
        audio,
        tracks,
        database,
        data_dir=settings.data_dir,
        embeddings_dir=settings.embeddings_dir,
        clock=SystemClock(),
        checkpoint_sha256=sha256_of(weights) if weights.is_file() else None,
        progress=progress,
    )
    report = builder.run(track_ids=track_ids, manifest_sha256=manifest_sha, force=args.force)
    print(
        json.dumps(
            {
                "embedding_version": report.embedding_version,
                "directory": str(report.directory),
                "requested": report.requested,
                "embedded": report.embedded,
                "from_cache": report.from_cache,
                "skipped_existing": report.skipped_existing,
                "failures": [f.model_dump() for f in report.failures[:50]],
                "failure_count": len(report.failures),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
