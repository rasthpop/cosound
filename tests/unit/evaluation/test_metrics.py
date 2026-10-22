import math

import pytest

from music_discovery.evaluation.metrics import (
    constraint_satisfaction,
    dcg,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

# judged relevance of a 6-track corpus for one query
REL = {1: 3, 2: 2, 3: 1, 4: 0, 5: 2, 6: 0}


def test_precision_uses_fixed_denominator() -> None:
    assert precision_at_k([1, 4, 2, 6, 3], REL) == pytest.approx(2 / 5)
    assert precision_at_k([1], REL) == pytest.approx(1 / 5), (
        "fewer than k results still divide by k"
    )
    assert precision_at_k([], REL) == 0.0
    assert precision_at_k([3, 4], REL, threshold=1) == pytest.approx(1 / 5)


def test_recall() -> None:
    assert recall_at_k([1, 4, 2, 6, 3], REL) == pytest.approx(2 / 3)  # relevant = {1, 2, 5}
    assert recall_at_k([4, 6], {4: 0, 6: 1}) is None, "no relevant tracks: undefined, not 0"


def test_ndcg_hand_computed() -> None:
    ranked = [4, 1, 2, 3, 5]
    actual = (
        0 / math.log2(2) + 3 / math.log2(3) + 2 / math.log2(4) + 1 / math.log2(5) + 2 / math.log2(6)
    )
    ideal = 3 / math.log2(2) + 2 / math.log2(3) + 2 / math.log2(4) + 1 / math.log2(5) + 0
    assert ndcg_at_k(ranked, REL) == pytest.approx(actual / ideal)
    assert ndcg_at_k([1, 2, 5, 3, 4], REL) == pytest.approx(1.0)
    assert ndcg_at_k([1, 2], {1: 0, 2: 0}) is None
    assert ndcg_at_k([9, 8], REL) == 0.0, "unjudged tracks have zero gain"


def test_ties_in_ideal_ordering() -> None:
    assert ndcg_at_k([5, 2, 1], {1: 3, 2: 2, 5: 2}) == pytest.approx(
        (2 + 2 / math.log2(3) + 3 / 2) / (3 + 2 / math.log2(3) + 2 / 2)
    )


def test_reciprocal_rank() -> None:
    assert reciprocal_rank([4, 6, 2], REL) == pytest.approx(1 / 3)
    assert reciprocal_rank([4, 6], REL) == 0.0
    assert reciprocal_rank([4], {4: 1}) is None


def test_constraint_satisfaction() -> None:
    rate = constraint_satisfaction(["yes", "no", None, "unknown", "yes", "yes"])
    assert rate is not None
    assert (rate.satisfied, rate.unknown, rate.violated, rate.n) == (0.4, 0.4, 0.2, 5)
    assert constraint_satisfaction([]) is None


def test_mean_skips_undefined() -> None:
    m = mean([1.0, None, 0.5])
    assert (m.value, m.n) == (0.75, 2)
    assert mean([None]).value is None
    assert dcg([]) == 0.0
