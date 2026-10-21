from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from music_discovery.audio.embedding_store import (
    EmbeddingFailure,
    EmbeddingMeta,
    NpyEmbeddingStore,
    embedding_version_for,
    read_failures,
    write_embeddings,
)
from music_discovery.domain.errors import EmbeddingVersionMismatch, InvalidEmbedding
from music_discovery.domain.protocols import EmbeddingStore
from music_discovery.domain.vectors import l2_normalize

PREP = {"sample_rate": 48000, "window_s": 10.0, "pooling": "mean"}


def meta(n: int, dim: int = 4, model: str = "clap-a", **kw: object) -> EmbeddingMeta:
    values: dict[str, object] = {
        "embedding_version": embedding_version_for(model, PREP),
        "model_id": model,
        "preprocessing": PREP,
        "package_versions": {"torch": "x"},
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "n": n,
        "dim": dim,
        "failures": 0,
    }
    values.update(kw)
    return EmbeddingMeta.model_validate(values)


def matrix(n: int, dim: int = 4) -> np.ndarray:
    return l2_normalize(np.random.default_rng(0).standard_normal((n, dim)))


def test_version_is_stable_and_sensitive() -> None:
    assert embedding_version_for("clap-a", PREP) == embedding_version_for("clap-a", dict(PREP))
    assert embedding_version_for("clap-a", PREP) != embedding_version_for("clap-b", PREP)
    assert embedding_version_for("clap-a", PREP) != embedding_version_for(
        "clap-a", {**PREP, "window_s": 5}
    )


def test_roundtrip_preserves_alignment(tmp_path: Path) -> None:
    ids = ["trk_b", "trk_a", "trk_c"]
    m = matrix(3)
    failures = [
        EmbeddingFailure(track_id="trk_x", path="raw/x.mp3", error_code="audio_decode_error")
    ]
    directory = write_embeddings(tmp_path, meta(3, failures=1), ids, m, failures)
    store = NpyEmbeddingStore.load(directory, expected_model_id="clap-a")
    assert isinstance(store, EmbeddingStore)
    assert store.track_ids() == ids
    np.testing.assert_array_equal(store.get("trk_a"), m[1])
    assert store.get("trk_missing") is None
    loaded_ids, loaded = store.matrix()
    assert loaded_ids == ids
    assert loaded.dtype == np.float32
    assert read_failures(directory) == failures
    assert store.embedding_version == embedding_version_for("clap-a", PREP)


def test_mismatched_model_is_refused(tmp_path: Path) -> None:
    directory = write_embeddings(tmp_path, meta(2), ["a", "b"], matrix(2))
    with pytest.raises(EmbeddingVersionMismatch):
        NpyEmbeddingStore.load(directory, expected_model_id="clap-b")


@pytest.mark.parametrize(
    ("ids", "rows", "kw"),
    [
        (["a", "b"], matrix(3), {}),
        (["a", "a"], matrix(2), {}),
        (["a", "b"], np.ones((2, 4), np.float32), {}),
        (["a", "b"], matrix(2, dim=5), {}),
    ],
)
def test_invalid_stores_are_rejected(
    tmp_path: Path, ids: list[str], rows: np.ndarray, kw: dict[str, object]
) -> None:
    with pytest.raises(InvalidEmbedding):
        write_embeddings(tmp_path, meta(len(ids), **kw), ids, rows)
    assert not any(tmp_path.iterdir()), "nothing written when validation fails"


def test_nan_rows_rejected(tmp_path: Path) -> None:
    rows = matrix(2)
    rows[1, 0] = np.nan
    with pytest.raises(InvalidEmbedding):
        write_embeddings(tmp_path, meta(2), ["a", "b"], rows)


def test_incomplete_version_is_not_loadable(tmp_path: Path) -> None:
    (tmp_path / "ev-partial").mkdir()
    with pytest.raises(InvalidEmbedding, match="no complete embedding version"):
        NpyEmbeddingStore.load(tmp_path / "ev-partial", expected_model_id=None)


def test_resolve_version_dir(tmp_path: Path) -> None:
    from music_discovery.audio.embedding_store import resolve_version_dir

    with pytest.raises(InvalidEmbedding, match="no embedding versions"):
        resolve_version_dir(tmp_path, None)
    old = write_embeddings(
        tmp_path, meta(1, created_at=datetime(2026, 1, 1, tzinfo=UTC)), ["a"], matrix(1)
    )
    new_meta = meta(
        1,
        model="clap-b",
        embedding_version=embedding_version_for("clap-b", PREP),
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    new = write_embeddings(tmp_path, new_meta, ["a"], matrix(1))
    assert resolve_version_dir(tmp_path, None) == new
    assert resolve_version_dir(tmp_path, old.name) == old
    with pytest.raises(InvalidEmbedding, match="not found"):
        resolve_version_dir(tmp_path, "ev-missing")
