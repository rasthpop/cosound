"""Local cache of raw source responses. Normalization reads from here, never from the network."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class RawCache:
    def __init__(self, root: Path) -> None:
        self._root = root

    def path(self, kind: str, key: str | int) -> Path:
        safe = str(key).replace("/", "_").replace(":", "_")
        return self._root / kind / f"{safe}.json"

    def get(self, kind: str, key: str | int) -> Any | None:
        path = self.path(kind, key)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, kind: str, key: str | int, payload: Any) -> None:
        """Atomic write: a crash never leaves a half-written cache entry."""
        path = self.path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

    def has(self, kind: str, key: str | int) -> bool:
        return self.path(kind, key).is_file()
