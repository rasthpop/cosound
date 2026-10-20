import pytest

from music_discovery.domain import errors
from music_discovery.domain.errors import MusicDiscoveryError


def all_error_classes() -> list[type[MusicDiscoveryError]]:
    found: list[type[MusicDiscoveryError]] = []
    pending: list[type[MusicDiscoveryError]] = [MusicDiscoveryError]
    while pending:
        cls = pending.pop()
        found.append(cls)
        pending.extend(cls.__subclasses__())
    return found


def test_codes_are_unique_and_snake_case() -> None:
    codes = [cls.code for cls in all_error_classes()]
    assert len(codes) == len(set(codes)), sorted(codes)
    for code in codes:
        assert code == code.lower()
        assert " " not in code


def test_every_subclass_overrides_code() -> None:
    for cls in all_error_classes():
        if cls is MusicDiscoveryError:
            continue
        assert "code" in cls.__dict__, f"{cls.__name__} must define its own code"


# base.md §16 failure cases that are raised as errors (the rest are states, see module doc).
SECTION_16 = {
    "Discogs rate limiting": errors.DiscogsRateLimited,
    "Discogs unavailable responses": errors.DiscogsUnavailable,
    "Missing or corrupt audio": (errors.AudioMissing, errors.AudioDecodeError),
    "CLAP model loading failures": errors.ModelLoadError,
    "Invalid embeddings": errors.InvalidEmbedding,
    "Missing vector-index entries": errors.IndexEntryMissing,
    "Invalid agent output": errors.AgentOutputError,
    "Invalid or contradictory hard constraints": (
        errors.InvalidConstraintError,
        errors.ContradictoryConstraintsError,
    ),
    "UMAP artifact mismatch": (errors.ProjectionMismatch, errors.ProjectionMissing),
    "Invalid feedback events": (
        errors.InvalidFeedbackEvent,
        errors.SessionNotFound,
        errors.QueryNotInSession,
        errors.TrackNotInResults,
    ),
}


@pytest.mark.parametrize("case", sorted(SECTION_16))
def test_section_16_cases_have_error_types(case: str) -> None:
    mapped = SECTION_16[case]
    classes = mapped if isinstance(mapped, tuple) else (mapped,)
    for cls in classes:
        assert issubclass(cls, MusicDiscoveryError)


def test_details_and_message() -> None:
    err = errors.TrackNotFound("Track trk_1 does not exist.", details={"track_id": "trk_1"})
    assert err.code == "track_not_found"
    assert err.message == "Track trk_1 does not exist."
    assert err.details == {"track_id": "trk_1"}
    assert isinstance(err, errors.NotFoundError)
    assert "track_not_found" in repr(err)


def test_rate_limited_carries_retry_after() -> None:
    err = errors.DiscogsRateLimited("slow down", retry_after_s=12.0)
    assert err.retry_after_s == 12.0
    assert isinstance(err, errors.DataSourceError)
