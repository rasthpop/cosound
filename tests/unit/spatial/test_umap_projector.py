from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from music_discovery.domain.errors import InvalidEmbedding
from music_discovery.domain.protocols import Matrix
from music_discovery.spatial import umap_projector
from music_discovery.spatial.umap_projector import (
    MapConfig,
    UmapParams,
    UmapProjector,
    effective_params,
    normalize_coordinates,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_n_neighbors_is_clamped_for_small_corpora() -> None:
    effective, notes = effective_params(UmapParams(n_neighbors=15), 20)
    assert effective.n_neighbors == 15
    assert notes == ["only 20 points: the projection is illustrative, not a quality claim"]

    effective, notes = effective_params(UmapParams(n_neighbors=15), 10)
    assert effective.n_neighbors == 9
    assert notes[0] == "n_neighbors clamped from 15 to 9 for n=10"

    effective, _ = effective_params(UmapParams(n_neighbors=15), 8000)
    assert effective == UmapParams(n_neighbors=15)


def test_too_few_points_raise() -> None:
    with pytest.raises(InvalidEmbedding, match="at least 4"):
        effective_params(UmapParams(), 3)


def test_normalization_maps_into_unit_box_and_is_recorded() -> None:
    raw = np.array([[2.0, 10.0], [6.0, 12.0], [4.0, 11.0]])
    coords, transform = normalize_coordinates(raw)
    assert coords.min() == pytest.approx(-1.0)
    assert np.abs(coords).max() == pytest.approx(1.0)
    center, scale = np.array(transform["center"]), transform["scale"]
    np.testing.assert_allclose(coords * scale + center, raw)
    assert transform["kind"] == "center_scale"


def test_config_file_loads_with_settings_values() -> None:
    config = MapConfig.load(REPO_ROOT / "config" / "umap.yaml", random_state=7, n_components=2)
    assert config.umap.random_state == 7
    assert config.umap.n_components == 2
    assert config.umap.metric == "cosine"
    assert config.normalize is True
    assert config.quality.k >= 1


def test_spectral_failure_falls_back_to_random_init(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "umap", types.ModuleType("umap"))
    calls: list[str] = []

    def fake_run(umap: Any, x: Matrix, params: UmapParams) -> np.ndarray:
        calls.append(params.init)
        if params.init == "spectral":
            raise ValueError("graph is not connected")
        return np.asarray(x[:, :2], dtype=np.float64)

    monkeypatch.setattr(UmapProjector, "_run", staticmethod(fake_run))
    x = np.eye(6, dtype=np.float32)
    projection = UmapProjector().fit(x, UmapParams(n_neighbors=15), normalize=False)

    assert calls == ["spectral", "random"]
    assert projection.requested.init == "spectral"
    assert projection.effective.init == "random"
    assert projection.effective.n_neighbors == 5
    assert any("used init=random" in note for note in projection.notes)
    assert projection.coordinate_transform is None
    assert "umap-learn" in projection.package_versions


def test_module_import_does_not_load_umap() -> None:
    assert "import umap" not in Path(umap_projector.__file__).read_text().split("def fit")[0]
