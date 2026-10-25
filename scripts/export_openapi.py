"""Write the API's OpenAPI schema to frontend/openapi.json (deterministic: sorted keys).

    uv run python scripts/export_openapi.py            # write
    uv run python scripts/export_openapi.py --check    # exit 1 if the file is out of date

The frontend generates its types from this file (P09); commit it with every contract change.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from music_discovery.api.app import build_app
from music_discovery.infrastructure.settings import REPO_ROOT, AppEnv, Settings

OUTPUT = REPO_ROOT / "frontend" / "openapi.json"


def openapi_document() -> dict[str, Any]:
    # explicit settings so the developer's .env (e.g. CORS origins) cannot change the output
    settings = Settings(_env_file=None, app_env=AppEnv.TEST)
    document: dict[str, Any] = build_app(settings).openapi()
    return document


def render() -> str:
    return json.dumps(openapi_document(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the file would change")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    text = render()
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.is_file() else ""
        if current != text:
            print(f"{args.output} is out of date; run scripts/export_openapi.py", file=sys.stderr)
            return 1
        return 0
    args.output.write_text(text, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
