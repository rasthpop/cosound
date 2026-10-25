from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from music_discovery.domain.errors import ProjectionMismatch, ProjectionMissing
from music_discovery.domain.schemas import ProjectionMeta
from music_discovery.infrastructure.spatial_store import COORDINATES_FILE, FileProjectionStore
from music_discovery.spatial.spatial_repository import (
    ProjectionSpatialRepository,
    load_projection,
    projection_version_for,
)

IDS = ["trk_a", "trk_b", "trk_c", "trk_d"]
COORDS = [(-1.0, 0.25), (0.1 + 0.2, -0.75), (1.0, 1.0), (0.0, -1.0)]
CATALOG = [*IDS, "trk_no_audio"]
T0 = datetime(2026, 10, 1, tzinfo=UTC)


def write(
    store: FileProjectionStore,
    version: str = "umap-aaa",
    *,
    ids: list[str] = IDS,
    embedding_version: str = "ev-1",
    created_at: datetime = T0,
) -> ProjectionMeta:
    coords = COORDS[: len(ids)]
    meta = ProjectionMeta(
        projection_version=version,
        embedding_version=embedding_version,
        model_id="fake-clap-v1",
        umap_requested={"n_neighbors": 15},
        umap_effective={"n_neighbors": 3},
        random_state=42,
        package_versions={"umap-learn": "0.5.12"},
        created_at=created_at,
        n_points=len(ids),
        excluded_tracks=1,
        coordinates_sha256=store.coordinates_sha256(ids, coords),
    )
    store.write(meta, ids, coords, {"trustworthiness": 0.9})
    return meta


def load(
    store: FileProjectionStore,
    version: str = "umap-aaa",
    *,
    embedded_track_ids: list[str] = IDS,
    catalog_track_ids: list[str] = CATALOG,
) -> ProjectionSpatialRepository:
    return load_projection(
        store,
        version,
        embedding_version="ev-1",
        embedded_track_ids=embedded_track_ids,
        catalog_track_ids=catalog_track_ids,
    )


def test_round_trip_is_exact_and_validated(tmp_path: Path) -> None:
    store = FileProjectionStore(tmp_path)
    meta = write(store)
    repo = load(store)
    assert repo.projection_version == "umap-aaa"
    assert repo.meta == meta
    assert repo.coordinates("trk_b") == COORDS[1]  # repr round-trip keeps 0.30000000000000004
    assert repo.coordinates("trk_no_audio") is None
    assert dict(repo.all_coordinates()) == dict(zip(IDS, COORDS, strict=True))
    assert (tmp_path / "umap-aaa" / "quality.json").is_file()


def test_absent_projection_is_missing(tmp_path: Path) -> None:
    with pytest.raises(ProjectionMissing):
        load(FileProjectionStore(tmp_path))
    with pytest.raises(ProjectionMissing):
        FileProjectionStore(tmp_path).resolve(None)


def test_other_embedding_version_is_a_mismatch(tmp_path: Path) -> None:
    store = FileProjectionStore(tmp_path)
    write(store, embedding_version="ev-old")
    with pytest.raises(ProjectionMismatch, match="ev-old") as info:
        load(store)
    assert info.value.details["stored"] == "ev-old"


def test_missing_and_extra_ids_are_mismatches(tmp_path: Path) -> None:
    store = FileProjectionStore(tmp_path)
    write(store, ids=IDS[:3])
    with pytest.raises(ProjectionMismatch, match="1 missing, 0 extra") as info:
        load(store)
    assert info.value.details["missing"] == ["trk_d"]
    with pytest.raises(ProjectionMismatch, match="0 missing, 1 extra"):
        load(store, embedded_track_ids=IDS[:2])


def test_ids_outside_the_catalog_are_a_mismatch(tmp_path: Path) -> None:
    store = FileProjectionStore(tmp_path)
    write(store)
    with pytest.raises(ProjectionMismatch, match="not in the catalog"):
        load(store, catalog_track_ids=IDS[:3])


def test_corrupted_coordinates_are_a_mismatch(tmp_path: Path) -> None:
    store = FileProjectionStore(tmp_path)
    write(store)
    path = tmp_path / "umap-aaa" / COORDINATES_FILE
    path.write_text(path.read_text().replace("trk_c,1.0", "trk_c,1.5"))
    with pytest.raises(ProjectionMismatch, match="sha256"):
        load(store)


def test_truncated_or_unreadable_files_are_mismatches(tmp_path: Path) -> None:
    store = FileProjectionStore(tmp_path)
    write(store)
    (tmp_path / "umap-aaa" / COORDINATES_FILE).unlink()
    with pytest.raises(ProjectionMismatch, match="cannot read"):
        load(store)
    (tmp_path / "umap-aaa" / "meta.json").write_text("{not json")
    with pytest.raises(ProjectionMismatch, match="unreadable projection meta"):
        load(store)


def test_resolve_prefers_active_then_newest(tmp_path: Path) -> None:
    store = FileProjectionStore(tmp_path)
    write(store, "umap-old", created_at=T0)
    write(store, "umap-new", created_at=T0 + timedelta(days=1))
    assert store.resolve(None) == "umap-new"
    assert store.resolve("umap-old") == "umap-old"
    with pytest.raises(ProjectionMissing, match="ACTIVE_PROJECTION_VERSION"):
        store.resolve("umap-gone")
    (tmp_path / "umap-new" / "meta.json").write_text("{broken")
    assert store.resolve(None) == "umap-old"  # a broken version is never picked implicitly


def test_projection_version_is_stable_and_content_addressed() -> None:
    config = {"umap": {"n_neighbors": 15, "min_dist": 0.1}, "normalize": True}
    reordered = {"normalize": True, "umap": {"min_dist": 0.1, "n_neighbors": 15}}
    version = projection_version_for("ev-1", config)
    assert version.startswith("umap-")
    assert version == projection_version_for("ev-1", reordered)
    assert version != projection_version_for("ev-2", config)


SEARCH_PATH_MODULES = [
    "music_discovery.retrieval.hybrid_retriever",
    "music_discovery.agents.orchestrator",
    "music_discovery.spatial.spatial_repository",
    "music_discovery.spatial.neighbor_service",
    "music_discovery.infrastructure.spatial_store",
]


def test_search_path_does_not_import_umap() -> None:
    code = (
        "import importlib, sys\n"
        f"for name in {SEARCH_PATH_MODULES!r}: importlib.import_module(name)\n"
        "loaded = sorted(m for m in sys.modules if m.split('.')[0] in {'umap', 'numba'})\n"
        "print(','.join(loaded))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == ""
