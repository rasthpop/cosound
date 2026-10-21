"""Download and unpack FMA archives into DATA_DIR/raw/fma (git-ignored).

    uv run python scripts/download_fma.py                 # metadata only (default)
    uv run python scripts/download_fma.py --subset small  # 7.2 GiB of 30 s clips

Checksums come from https://github.com/mdeff/fma. Re-running skips verified downloads.
"""

from __future__ import annotations

import argparse
import sys

import httpx

from music_discovery.infrastructure.settings import get_settings
from music_discovery.ingestion.archives import FMA_ARCHIVES, download, extract


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--subset", choices=sorted(FMA_ARCHIVES), action="append")
    args = parser.parse_args()
    target = get_settings().raw_dir / "fma"
    with httpx.Client(timeout=httpx.Timeout(30.0, read=300.0)) as http:
        for name in args.subset or ["metadata"]:
            archive = FMA_ARCHIVES[name]
            zip_path = download(archive, target, http)
            print(f"verified {zip_path}")
            print(f"extracted {extract(archive, zip_path, target)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
