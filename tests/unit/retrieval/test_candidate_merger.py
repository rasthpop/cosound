from music_discovery.domain.enums import RetrievalSource
from music_discovery.retrieval.candidate_merger import RankedScore, backfill, merge, missing


def scores(*pairs: tuple[str, float]) -> list[RankedScore]:
    return [RankedScore(t, s, i) for i, (t, s) in enumerate(pairs, start=1)]


def test_union_dedupes_and_keeps_provenance() -> None:
    result = merge(
        {
            "metadata": scores(("trk_a", 9.0), ("trk_b", 4.0)),
            "semantic": scores(("trk_b", 0.6), ("trk_c", 0.5)),
        },
        pool_size=10,
    )
    by_id = {c.track_id: c for c in result.candidates}
    assert sorted(by_id) == ["trk_a", "trk_b", "trk_c"]
    b = by_id["trk_b"]
    assert b.raw("metadata") == 4.0
    assert b.raw("semantic") == 0.6
    assert b.signals["metadata"].rank == 2
    assert b.signals["semantic"].rank == 1
    assert b.retrieval_sources == [RetrievalSource.METADATA, RetrievalSource.SEMANTIC]
    assert by_id["trk_a"].raw("semantic") is None, "not retrieved yet; not zero"


def test_pool_cap_keeps_best_ranked_from_any_source() -> None:
    result = merge(
        {
            "metadata": scores(("m1", 3.0), ("m2", 2.0), ("m3", 1.0)),
            "semantic": scores(("s1", 0.9), ("s2", 0.8), ("s3", 0.7)),
        },
        pool_size=4,
    )
    assert [c.track_id for c in result.candidates] == ["m1", "s1", "m2", "s2"]
    assert result.pool_before_cap == 6


def test_backfill_distinguishes_scored_from_not_available() -> None:
    result = merge({"metadata": scores(("with_audio", 5.0), ("no_audio", 3.0))}, pool_size=10)
    assert missing(result.candidates, "semantic") == ["with_audio", "no_audio"]
    backfill(
        result.candidates, "semantic", {"with_audio": 0.21}, evaluated={"with_audio", "no_audio"}
    )
    by_id = {c.track_id: c for c in result.candidates}
    assert by_id["with_audio"].signals["semantic"].status == "backfilled"
    assert by_id["with_audio"].raw("semantic") == 0.21
    assert by_id["no_audio"].signals["semantic"].status == "not_available"
    assert by_id["no_audio"].raw("semantic") is None
    assert by_id["with_audio"].retrieval_sources == [RetrievalSource.METADATA], (
        "back-fill is not retrieval"
    )


def test_backfill_zero_is_a_real_score() -> None:
    result = merge({"semantic": scores(("t", 0.5))}, pool_size=10)
    backfill(result.candidates, "metadata", {"t": 0.0}, evaluated={"t"})
    assert result.candidates[0].signals["metadata"].status == "backfilled"
    assert result.candidates[0].raw("metadata") == 0.0


def test_backfill_never_overwrites_and_skips_unevaluated() -> None:
    result = merge({"semantic": scores(("t", 0.5)), "metadata": scores(("t", 2.0))}, pool_size=10)
    backfill(result.candidates, "semantic", {"t": 0.99}, evaluated={"t"})
    assert result.candidates[0].raw("semantic") == 0.5
    other = merge({"semantic": scores(("u", 0.5))}, pool_size=10)
    backfill(other.candidates, "metadata", {}, evaluated=set())
    assert "metadata" not in other.candidates[0].signals
