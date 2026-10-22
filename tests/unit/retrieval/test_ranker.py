import pytest

from music_discovery.retrieval.candidate_merger import Candidate, SignalValue
from music_discovery.retrieval.config import RetrievalConfig, SignalWeights
from music_discovery.retrieval.ranker import rank

CONFIG = RetrievalConfig(
    weights_version="w-test", weights=SignalWeights(semantic=0.6, metadata=0.4)
)
BOTH = {"semantic", "metadata"}


def cand(tid: str) -> Candidate:
    return Candidate(tid, {"semantic": SignalValue(0.5, 1, "retrieved")})


def ranked(normalized: dict, config: RetrievalConfig = CONFIG, **kw: object) -> dict[str, float]:  # type: ignore[type-arg]
    ids = sorted({t for values in normalized.values() for t in values})
    result = rank(
        [cand(t) for t in ids],
        normalized,
        config,
        active=kw.pop("active", BOTH),
        normalization="n",
        **kw,
    )  # type: ignore[arg-type]
    return {s.candidate.track_id: s.relevance for s in result}


def test_weighted_sum_when_all_signals_present() -> None:
    scores = ranked({"semantic": {"a": 1.0}, "metadata": {"a": 0.5}})
    assert scores["a"] == pytest.approx(0.6 * 1.0 + 0.4 * 0.5)


def test_missing_semantic_renormalizes_over_metadata() -> None:
    scores = ranked(
        {"semantic": {"audio": 0.9, "no_audio": None}, "metadata": {"audio": None, "no_audio": 0.9}}
    )
    assert scores["audio"] == pytest.approx(0.9)
    assert scores["no_audio"] == pytest.approx(0.9), (
        "metadata-only tracks are not punished for missing audio"
    )


def test_evaluated_low_semantic_is_not_missing_semantic() -> None:
    scores = ranked({"semantic": {"low": 0.0, "none": None}, "metadata": {"low": 0.8, "none": 0.8}})
    assert scores["low"] == pytest.approx(0.4 * 0.8)
    assert scores["none"] == pytest.approx(0.8)
    assert scores["none"] > scores["low"]


def test_coverage_penalty_prefers_fully_evidenced_tracks() -> None:
    config = CONFIG.model_copy(update={"coverage_penalty_gamma": 1.0})
    scores = ranked(
        {"semantic": {"both": 0.8, "meta_only": None}, "metadata": {"both": 0.8, "meta_only": 0.8}},
        config,
    )
    assert scores["both"] == pytest.approx(0.8)
    assert scores["meta_only"] == pytest.approx(0.8 * 0.4)


def test_relationship_weight_zero_by_default_has_no_effect() -> None:
    norm = {"semantic": {"a": 0.5}, "metadata": {"a": 0.5}, "relationship": {"a": 1.0}}
    assert ranked(norm, active={"semantic", "metadata", "relationship"})["a"] == pytest.approx(0.5)
    result = rank(
        [cand("a")],
        norm,
        CONFIG,
        active={"semantic", "metadata", "relationship"},
        normalization="n",
    )
    assert result[0].breakdown.relationship is None


def test_inactive_signals_are_ignored_and_unscorable_dropped() -> None:
    norm = {"semantic": {"a": 0.2, "b": None}, "metadata": {"a": 1.0, "b": 1.0}}
    assert ranked(norm, active={"semantic"}) == {"a": pytest.approx(0.2)}, (
        "b has no semantic signal"
    )


def test_penalties_and_demotion() -> None:
    norm = {"semantic": {"a": 1.0, "b": 1.0}, "metadata": {"a": 1.0, "b": 1.0}}
    assert ranked(norm, penalties={"a": 0.3})["a"] == pytest.approx(0.7)
    assert ranked(norm, penalties={"a": 5.0})["a"] == 0.0, "clipped at 0"
    demote = CONFIG.model_copy(
        update={"constraints": CONFIG.constraints.model_copy(update={"unknown": "demote"})}
    )
    assert ranked(norm, demote, unknown_constraints={"b": 2})["b"] == pytest.approx(0.25)
    assert ranked(norm, unknown_constraints={"b": 2})["b"] == pytest.approx(1.0), (
        "keep_flagged does not demote"
    )


def test_order_breakdown_and_ties() -> None:
    norm = {
        "semantic": {"b": 0.5, "a": 0.5, "c": 0.9},
        "metadata": {"a": None, "b": None, "c": None},
    }
    result = rank(
        [cand(t) for t in "bac"], norm, CONFIG, active=BOTH, normalization="semantic=minmax"
    )
    assert [s.candidate.track_id for s in result] == ["c", "a", "b"]
    breakdown = result[0].breakdown
    assert breakdown.semantic == 0.9
    assert breakdown.metadata is None, "missing stays None in the breakdown"
    assert breakdown.weights_version == "w-test"
    assert breakdown.normalization == "semantic=minmax"
