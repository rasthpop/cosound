"""Seeded UMAP projection of the feature matrix (base.md §11.2).

Called only from `scripts/build_map.py`; the request path reads persisted coordinates and
never imports this module's UMAP dependency (it is imported lazily inside `fit`).

Coordinates are visualization coordinates without units (base.md §11.4). With `normalize`
they are centered and scaled into [-1, 1]; the transform is recorded so it can be undone.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np
import numpy.typing as npt
import yaml
from pydantic import BaseModel, ConfigDict, Field

from music_discovery.domain.errors import InvalidEmbedding
from music_discovery.domain.protocols import Matrix

log = logging.getLogger(__name__)

Coordinates = npt.NDArray[np.float64]
"""Projected points, shape (n, n_components)."""

MIN_POINTS = 4
"""UMAP needs at least a few points to build a neighbor graph; fewer is an error."""


class _Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class UmapParams(_Config):
    n_components: int = Field(default=2, ge=2, le=3)
    n_neighbors: int = Field(default=15, ge=2)
    min_dist: float = Field(default=0.1, ge=0.0)
    metric: Literal["cosine", "euclidean"] = "cosine"
    init: Literal["spectral", "random"] = "spectral"
    random_state: int = 42


class QualityConfig(_Config):
    k: int = Field(default=10, ge=1)
    """Neighborhood size for trustworthiness and kNN overlap."""
    probe_tracks: int = Field(default=3, ge=0)
    probe_neighbors: int = Field(default=3, ge=1)


class MapConfig(_Config):
    """config/umap.yaml; `random_state` and `n_components` come from settings (UMAP_*)."""

    umap: UmapParams = UmapParams()
    normalize: bool = True
    quality: QualityConfig = QualityConfig()

    @classmethod
    def load(cls, path: Path, *, random_state: int, n_components: int) -> MapConfig:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        umap_raw = {**raw.get("umap", {}), "random_state": random_state}
        umap_raw["n_components"] = n_components
        return cls.model_validate({**raw, "umap": umap_raw})


@dataclass(frozen=True)
class Projection:
    coordinates: Coordinates
    requested: UmapParams
    effective: UmapParams
    """What was actually run: `n_neighbors` clamped for small n, `init` after any fallback."""
    coordinate_transform: dict[str, Any] | None
    package_versions: dict[str, str]
    notes: list[str] = field(default_factory=list)


class Projector(Protocol):
    def fit(self, matrix: Matrix, params: UmapParams, *, normalize: bool) -> Projection: ...


def effective_params(params: UmapParams, n: int) -> tuple[UmapParams, list[str]]:
    """Clamp parameters that UMAP cannot honor for `n` points, with a note per change."""
    if n < MIN_POINTS:
        raise InvalidEmbedding(f"a projection needs at least {MIN_POINTS} points, got {n}")
    notes = []
    effective = params
    if params.n_neighbors >= n:
        effective = params.model_copy(update={"n_neighbors": n - 1})
        notes.append(f"n_neighbors clamped from {params.n_neighbors} to {n - 1} for n={n}")
    if n < 100:
        notes.append(f"only {n} points: the projection is illustrative, not a quality claim")
    return effective, notes


def normalize_coordinates(coords: Coordinates) -> tuple[Coordinates, dict[str, Any]]:
    """Center the bounding box at 0 and scale the largest half-extent to 1."""
    low, high = coords.min(axis=0), coords.max(axis=0)
    center = (low + high) / 2
    scale = float(np.max((high - low) / 2))
    if scale <= 0:
        scale = 1.0
    transform = {
        "kind": "center_scale",
        "center": [float(c) for c in center],
        "scale": scale,
        "formula": "(raw - center) / scale",
    }
    return (coords - center) / scale, transform


class UmapProjector:
    def fit(self, matrix: Matrix, params: UmapParams, *, normalize: bool) -> Projection:
        import umap  # heavy (numba); kept out of import time on purpose

        x = np.asarray(matrix, dtype=np.float32)
        effective, notes = effective_params(params, x.shape[0])
        try:
            coords = self._run(umap, x, effective)
        except Exception as exc:  # spectral init fails on tiny or disconnected graphs
            if effective.init != "spectral":
                raise
            log.warning("spectral init failed (%s); retrying with init=random", exc)
            notes.append(f"spectral init failed ({type(exc).__name__}); used init=random")
            effective = effective.model_copy(update={"init": "random"})
            coords = self._run(umap, x, effective)

        transform = None
        if normalize:
            coords, transform = normalize_coordinates(coords)
        return Projection(
            coordinates=coords,
            requested=params,
            effective=effective,
            coordinate_transform=transform,
            package_versions=_package_versions(),
            notes=notes,
        )

    @staticmethod
    def _run(umap: Any, x: Matrix, params: UmapParams) -> Coordinates:
        reducer = umap.UMAP(
            n_components=params.n_components,
            n_neighbors=params.n_neighbors,
            min_dist=params.min_dist,
            metric=params.metric,
            init=params.init,
            random_state=params.random_state,
            transform_seed=params.random_state,
            n_jobs=1,  # a fixed random_state disables parallelism anyway
        )
        with warnings.catch_warnings():
            # small graphs make UMAP warn about its own spectral fallback; recorded in notes
            warnings.simplefilter("ignore", UserWarning)
            coords = reducer.fit_transform(x)
        result = np.asarray(coords, dtype=np.float64)
        if not np.all(np.isfinite(result)):
            raise InvalidEmbedding("UMAP produced non-finite coordinates")
        return result


def _package_versions() -> dict[str, str]:
    import importlib.metadata as md

    return {name: md.version(name) for name in ("umap-learn", "numpy", "scikit-learn", "numba")}
