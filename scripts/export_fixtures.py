"""Write the contract examples (api/examples.py) as frontend mock fixtures.

    uv run python scripts/export_fixtures.py            # write frontend/src/mocks/fixtures/
    uv run python scripts/export_fixtures.py --check    # exit 1 if any fixture is out of date

One `<name>.json` per example plus `index.json` (fixture name → DTO schema name), so mocks
and tests know which schema each fixture follows. Stale fixtures are removed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from music_discovery.api.examples import build_examples
from music_discovery.infrastructure.settings import REPO_ROOT

OUTPUT_DIR = REPO_ROOT / "frontend" / "src" / "mocks" / "fixtures"
INDEX = "index.json"


def _dump(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render() -> dict[str, str]:
    """File name → content."""
    examples = build_examples()
    files = {f"{name}.json": _dump(m.model_dump(mode="json")) for name, m in examples.items()}
    files[INDEX] = _dump({name: type(m).__name__ for name, m in sorted(examples.items())})
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if any fixture would change")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    files = render()
    existing = {p.name: p for p in args.output.glob("*.json")} if args.output.is_dir() else {}
    stale = sorted(set(existing) - set(files))
    changed = sorted(
        name for name, text in files.items()
        if name not in existing or existing[name].read_text(encoding="utf-8") != text
    )  # fmt: skip
    if args.check:
        if stale or changed:
            print(f"fixtures out of date: {changed + stale}; run scripts/export_fixtures.py",
                  file=sys.stderr)  # fmt: skip
            return 1
        return 0
    args.output.mkdir(parents=True, exist_ok=True)
    for name in changed:
        (args.output / name).write_text(files[name], encoding="utf-8")
    for name in stale:
        existing[name].unlink()
    print(f"{len(files)} fixtures in {args.output} ({len(changed)} written, {len(stale)} removed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
