"""Create (once) or check the fixed 20-track FMA evaluation manifest.

    uv run python scripts/make_fma_manifest.py                # write the manifest
    uv run python scripts/make_fma_manifest.py --check-audio  # probe the audio files listed in it

The manifest is generated once and reused. Re-running with the same inputs reproduces it
byte-for-byte; writing a *different* manifest over an existing one needs --force.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from music_discovery.audio.audio_probe import SoundfileProbe
from music_discovery.infrastructure.settings import get_settings
from music_discovery.ingestion.fma_loader import load_echonest, load_genres, load_tracks
from music_discovery.ingestion.fma_manifest import read_manifest, render_manifest, select_manifest

SEED = 42
AUDIO_DIR_REL = Path("raw/fma/fma_small")


def check_audio(manifest: Path, data_dir: Path) -> int:
    probe = SoundfileProbe()
    bad = 0
    for row in read_manifest(manifest):
        result = probe.probe(data_dir / row["audio_path"])
        status = "ok" if result.ok else result.error_code
        bad += not result.ok
        print(f"{row['fma_track_id']:>7}  {status:<20} {row['audio_path']}")
    print(
        f"\n{bad} of the listed files are missing or unusable."
        if bad
        else "\nall audio files decode."
    )
    return 1 if bad else 0


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--output", type=Path, default=settings.evaluation_dir / "fma_20_manifest.csv"
    )
    parser.add_argument(
        "--metadata-dir", type=Path, default=settings.raw_dir / "fma" / "fma_metadata"
    )
    parser.add_argument(
        "--force", action="store_true", help="replace a different existing manifest"
    )
    parser.add_argument("--check-audio", action="store_true")
    args = parser.parse_args()

    if args.check_audio:
        return check_audio(args.output, settings.data_dir)

    records = load_tracks(args.metadata_dir, subset="small")
    rows = select_manifest(
        records,
        genres=load_genres(args.metadata_dir),
        echonest=load_echonest(args.metadata_dir, [r.fma_track_id for r in records]),
        seed=SEED,
    )
    content = render_manifest(rows, audio_dir_rel=AUDIO_DIR_REL)
    if args.output.exists():
        if args.output.read_text(encoding="utf-8") == content:
            print(f"{args.output} is already up to date (identical output).")
            return 0
        if not args.force:
            print(
                f"{args.output} exists and differs; refusing to overwrite without --force.",
                file=sys.stderr,
            )
            return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"wrote {len(rows)} tracks to {args.output}")
    print("themes:", dict(Counter(r.theme for r in rows)))
    print("top genres:", dict(sorted(Counter(r.record.genre_top or "-" for r in rows).items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
