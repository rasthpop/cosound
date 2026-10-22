import pytest

from music_discovery.retrieval.config import CalibratedParams
from music_discovery.retrieval.normalization import normalize

SCORES = {"a": 0.62, "b": 0.50, "c": 0.44, "missing": None}


def test_minmax() -> None:
    result = normalize(SCORES, "minmax")
    assert result.values["a"] == pytest.approx(1.0)
    assert result.values["c"] == pytest.approx(0.0)
    assert result.values["b"] == pytest.approx((0.50 - 0.44) / 0.18)
    assert result.values["missing"] is None
    assert result.fallback is None


def test_max_scale_keeps_zero_as_zero() -> None:
    result = normalize({"a": 8.0, "b": 2.0, "c": 0.0, "d": None}, "max_scale")
    assert result.values == {"a": 1.0, "b": 0.25, "c": 0.0, "d": None}
    nothing = normalize({"a": 0.0, "b": 0.0}, "max_scale")
    assert nothing.values == {"a": 0.0, "b": 0.0}, "no match anywhere stays 0, not rescaled"


def test_rank_with_ties() -> None:
    result = normalize({"a": 3.0, "b": 3.0, "c": 1.0, "d": None}, "rank")
    assert result.values == {"a": 0.75, "b": 0.75, "c": 0.0, "d": None}
    assert normalize({"only": 0.1}, "rank").values == {"only": 1.0}


def test_zscore_sigmoid_is_monotonic_and_bounded() -> None:
    result = normalize(SCORES, "zscore_sigmoid")
    a, b, c = (result.values[k] for k in "abc")
    assert a is not None
    assert b is not None
    assert c is not None
    assert 0 < c < b < a < 1


def test_calibrated() -> None:
    params = CalibratedParams(slope=10.0, intercept=-5.0)
    result = normalize({"x": 0.5, "y": 0.9, "z": None}, "calibrated", calibrated=params)
    assert result.values["x"] == pytest.approx(0.5)
    assert result.values["y"] == pytest.approx(1 / (1 + 2.718281828**-4), rel=1e-6)
    assert result.values["z"] is None
    with pytest.raises(ValueError, match="fitted parameters"):
        normalize({"x": 0.5}, "calibrated")


@pytest.mark.parametrize("strategy", ["minmax", "zscore_sigmoid"])
def test_degenerate_pools_fall_back_to_rank(strategy: str) -> None:
    small = normalize({"a": 0.6, "b": 0.5}, strategy, min_pool=3)  # type: ignore[arg-type]
    assert small.strategy == "rank"
    assert small.fallback == f"{strategy}->rank:pool_too_small"
    assert small.values == {"a": 1.0, "b": 0.0}
    flat = normalize({"a": 0.5, "b": 0.5, "c": 0.5}, strategy)  # type: ignore[arg-type]
    assert flat.fallback == f"{strategy}->rank:no_spread"
    assert set(flat.values.values()) == {0.5}


def test_all_missing() -> None:
    assert normalize({"a": None}, "minmax").values == {"a": None}
