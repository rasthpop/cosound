"""File-based projection store (implements `domain.protocols.ProjectionStore`).

Layout of one version::

    artifacts/umap/{projection_version}/
    ├── coordinates.csv   track_id,x,y   (row order = the projection's track order)
    ├── quality.json      neighborhood-preservation metrics and the manual probe table
    └── meta.json         ProjectionMeta, incl. the sha256 of coordinates.csv

`meta.json` is written last, so its presence marks a complete version. Floats are written with
`repr`, which round-trips exactly, so the content hash is stable across write and read.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from pydantic import ValidationError

from music_discovery.domain.errors import ProjectionMismatch, ProjectionMissing
from music_discovery.domain.schemas import ProjectionArtifact, ProjectionMeta

COORDINATES_FILE = "coordinates.csv"
QUALITY_FILE = "quality.json"
META_FILE = "meta.json"
HEADER = ["track_id", "x", "y"]


def _atomic_write(path: Path, write: Callable[[Path], object]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    write(tmp)
    os.replace(tmp, path)


def _serialize(track_ids: Sequence[str], coordinates: Sequence[tuple[float, float]]) -> str:
    if len(track_ids) != len(coordinates):
        raise ValueError(f"{len(coordinates)} coordinates for {len(track_ids)} track ids")
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    for track_id, (x, y) in zip(track_ids, coordinates, strict=True):
        writer.writerow([track_id, repr(float(x)), repr(float(y))])
    return buffer.getvalue()


class FileProjectionStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def coordinates_sha256(
        self, track_ids: Sequence[str], coordinates: Sequence[tuple[float, float]]
    ) -> str:
        return hashlib.sha256(_serialize(track_ids, coordinates).encode("utf-8")).hexdigest()

    def write(
        self,
        meta: ProjectionMeta,
        track_ids: Sequence[str],
        coordinates: Sequence[tuple[float, float]],
        quality: Mapping[str, object],
    ) -> None:
        text = _serialize(track_ids, coordinates)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest != meta.coordinates_sha256:
            raise ValueError("meta.coordinates_sha256 does not match the coordinates")
        directory = self._root / meta.projection_version
        directory.mkdir(parents=True, exist_ok=True)
        (directory / META_FILE).unlink(missing_ok=True)  # incomplete until rewritten
        _atomic_write(directory / COORDINATES_FILE, lambda tmp: tmp.write_text(text, "utf-8"))
        _atomic_write(
            directory / QUALITY_FILE,
            lambda tmp: tmp.write_text(json.dumps(quality, indent=2), "utf-8"),
        )
        _atomic_write(
            directory / META_FILE, lambda tmp: tmp.write_text(meta.model_dump_json(indent=2))
        )

    def read(self, projection_version: str) -> ProjectionArtifact:
        directory = self._root / projection_version
        meta = self._meta(directory)
        if meta is None:
            raise ProjectionMissing(
                f"no projection {projection_version} under {self._root}; run scripts/build_map.py",
                details={"projection_version": projection_version},
            )
        if meta.projection_version != projection_version:
            raise ProjectionMismatch(
                f"{directory} holds projection {meta.projection_version}",
                details={"projection_version": projection_version},
            )
        path = directory / COORDINATES_FILE
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProjectionMismatch(f"cannot read {path}: {exc}") from exc
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != meta.coordinates_sha256:
            raise ProjectionMismatch(
                f"{path} does not match the sha256 in meta.json (corrupted or edited)",
                details={"projection_version": projection_version},
            )
        track_ids, coordinates = self._parse(path, text)
        try:
            return ProjectionArtifact(meta=meta, track_ids=track_ids, coordinates=coordinates)
        except ValidationError as exc:
            raise ProjectionMismatch(f"invalid projection rows in {path}: {exc}") from exc

    def resolve(self, active: str | None) -> str:
        if active:
            if self._meta(self._root / active) is None:
                raise ProjectionMissing(
                    f"ACTIVE_PROJECTION_VERSION {active} not found under {self._root}",
                    details={"projection_version": active},
                )
            return active
        metas = []
        for directory in sorted(self._root.glob("umap-*")):
            try:
                meta = self._meta(directory)
            except ProjectionMismatch:
                continue  # an unreadable version is never picked implicitly
            if meta is not None:
                metas.append(meta)
        if not metas:
            raise ProjectionMissing(f"no projections under {self._root}; run scripts/build_map.py")
        return max(metas, key=lambda m: (m.created_at, m.projection_version)).projection_version

    @staticmethod
    def _meta(directory: Path) -> ProjectionMeta | None:
        path = directory / META_FILE
        if not path.is_file():
            return None
        try:
            return ProjectionMeta.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            raise ProjectionMismatch(f"unreadable projection meta {path}: {exc}") from exc

    @staticmethod
    def _parse(path: Path, text: str) -> tuple[list[str], list[tuple[float, float]]]:
        rows = list(csv.reader(io.StringIO(text)))
        if not rows or rows[0] != HEADER:
            raise ProjectionMismatch(f"{path} must start with the header {','.join(HEADER)}")
        track_ids: list[str] = []
        coordinates: list[tuple[float, float]] = []
        for line, row in enumerate(rows[1:], start=2):
            try:
                track_id, x, y = row
                coordinates.append((float(x), float(y)))
            except ValueError as exc:
                raise ProjectionMismatch(f"{path}:{line}: malformed row {row!r}") from exc
            track_ids.append(track_id)
        return track_ids, coordinates
