import pytest

from music_discovery.domain.enums import ConstraintStatus, DataSource
from music_discovery.domain.models import Provenance, Track
from music_discovery.domain.schemas import HardConstraint
from music_discovery.retrieval.config import ConstraintConfig
from music_discovery.retrieval.constraints import (
    apply_constraints,
    describe,
    evaluate,
    no_confident_match_reasons,
)

FMA = Provenance(source=DataSource.FMA)
S, V, U = ConstraintStatus.SATISFIED, ConstraintStatus.VIOLATED, ConstraintStatus.UNKNOWN


def track(
    tid: str,
    genres: list[str] | None = None,
    year: int | None = None,
    duration: float | None = 200.0,
) -> Track:
    return Track(
        id=tid, title=tid, genres=genres or [], year=year, duration_seconds=duration, provenance=FMA
    )


def c(**kw: object) -> HardConstraint:
    return HardConstraint.model_validate(kw)


NO_VOCALS = c(attribute="vocals", operator="excluded")
VOCALS = c(attribute="vocals", operator="required")

INSTRUMENTAL = track("instr", ["Instrumental", "Ambient"], year=2014)
POP = track("pop", ["Pop", "Synth Pop"], year=1985)
BARE = track("bare", [], year=None, duration=None)


@pytest.mark.parametrize(
    ("constraint", "t", "status"),
    [
        (NO_VOCALS, INSTRUMENTAL, S),
        (VOCALS, INSTRUMENTAL, V),
        (NO_VOCALS, POP, U),  # no vocal credits in the catalog: cannot claim compliance
        (VOCALS, POP, U),
        (
            c(attribute="genre", operator="required", value="electronic"),
            track("t", ["Ambient Electronic"]),
            S,
        ),
        (c(attribute="genre", operator="required", value="jazz"), POP, V),
        (c(attribute="genre", operator="excluded", value="pop"), POP, V),
        (c(attribute="genre", operator="excluded", value="jazz"), POP, S),
        (c(attribute="genre", operator="required", value="jazz"), BARE, U),
        (
            c(attribute="genre", operator="required", value="drum and bass"),
            track("t", ["Drum & Bass"]),
            S,
        ),
        (c(attribute="era", operator="range", range=[1980, 1989]), POP, S),
        (c(attribute="era", operator="range", range=[None, 1990]), INSTRUMENTAL, V),
        (c(attribute="era", operator="range", range=[1980, None]), BARE, U),
        (c(attribute="duration", operator="range", range=[None, 180]), POP, V),
        (c(attribute="duration", operator="range", range=[None, 180]), BARE, U),
        (c(attribute="instrument", operator="required", value="flute"), INSTRUMENTAL, U),
        (c(attribute="tempo", operator="range", range=[120, None]), POP, U),
    ],
)
def test_evaluate(constraint: HardConstraint, t: Track, status: ConstraintStatus) -> None:
    result = evaluate(constraint, t)
    assert result.status is status
    assert bool(result.evidence) == (status is not U), "decisions cite evidence; unknowns cite none"


CATALOG = {t.id: t for t in (INSTRUMENTAL, POP, BARE)}


def test_violators_are_excluded_regardless_of_order() -> None:
    outcome = apply_constraints(["pop", "instr", "bare"], CATALOG, [VOCALS], ConstraintConfig())
    assert outcome.kept == ["pop", "bare"]
    assert list(outcome.excluded) == ["instr"]


@pytest.mark.parametrize(
    ("policy", "kept"),
    [
        ("keep_flagged", ["instr", "pop", "bare"]),
        ("demote", ["instr", "pop", "bare"]),
        ("exclude", ["instr"]),
    ],
)
def test_unknown_policy(policy: str, kept: list[str]) -> None:
    outcome = apply_constraints(
        list(CATALOG), CATALOG, [NO_VOCALS], ConstraintConfig(unknown=policy)
    )  # type: ignore[arg-type]
    assert outcome.kept == kept
    assert outcome.unknown_count("pop") == 1
    assert outcome.unknown_count("instr") == 0


def test_missing_track_is_unknown_not_satisfied() -> None:
    outcome = apply_constraints(["ghost"], CATALOG, [NO_VOCALS], ConstraintConfig())
    assert outcome.results["ghost"][0].status is U


def test_no_constraints_keeps_everything() -> None:
    assert apply_constraints(["a", "b"], {}, [], ConstraintConfig()).kept == ["a", "b"]


def test_no_confident_match_reasons() -> None:
    jazz = c(attribute="genre", operator="required", value="jazz")
    outcome = apply_constraints(
        list(CATALOG), CATALOG, [jazz, NO_VOCALS], ConstraintConfig(unknown="exclude")
    )
    assert outcome.kept == []
    assert no_confident_match_reasons(outcome, [jazz, NO_VOCALS]) == [
        "genre jazz required: 0 satisfied, 2 violated, 1 unknown",
        "vocals excluded: 1 satisfied, 0 violated, 2 unknown",
    ]
    assert describe(c(attribute="era", operator="range", range=[None, 1990])) == "era in [, 1990]"
