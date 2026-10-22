import numpy as np
import pytest

from music_discovery.domain.errors import InvalidEmbedding
from music_discovery.domain.vectors import cosine, is_unit_norm, l2_normalize


def test_normalizes_vectors_and_rows() -> None:
    v = l2_normalize([3.0, 4.0])
    np.testing.assert_allclose(v, [0.6, 0.8], rtol=1e-6)
    assert v.dtype == np.float32
    m = l2_normalize([[1.0, 0.0], [0.0, 2.0], [1.0, 1.0]])
    assert is_unit_norm(m)
    assert m.shape == (3, 2)


@pytest.mark.parametrize(
    "bad",
    [[0.0, 0.0], [np.nan, 1.0], [np.inf, 1.0], [[1.0, 0.0], [0.0, 0.0]], [], [[[1.0]]]],
)
def test_invalid_vectors_raise(bad: object) -> None:
    with pytest.raises(InvalidEmbedding):
        l2_normalize(bad)  # type: ignore[arg-type]


def test_cosine() -> None:
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([1, 0], [-2, 0]) == pytest.approx(-1.0)
    assert cosine([1, 1], [2, 2]) == pytest.approx(1.0)
    with pytest.raises(InvalidEmbedding):
        cosine([1, 0], [1, 0, 0])
    with pytest.raises(InvalidEmbedding):
        cosine([0, 0], [1, 0])
