"""Create the fixed dev/test query split once (data/evaluation/split.json).

    uv run python scripts/make_split.py

Splits by query family (a query and its rephrasings stay on one side), seed 42.
Refuses to overwrite an existing split: the split is fixed for the life of the evaluation.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from music_discovery.evaluation.datasets import SPLIT_FILE, load_dataset, make_split
from music_discovery.infrastructure.settings import get_settings

SEED = 42


def main() -> int:
    directory = get_settings().evaluation_dir
    out = directory / SPLIT_FILE
    if out.exists():
        print(f"{out} already exists; the split is fixed for the life of the evaluation.")
        return 1
    dataset = load_dataset(directory, require_split=False)
    created_at = datetime.now(UTC).replace(microsecond=0)
    split = make_split(dataset.queries, seed=SEED, created_at=created_at)
    out.write_text(split.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"dev  ({len(split.dev)}): {split.dev}\ntest ({len(split.test)}): {split.test}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
