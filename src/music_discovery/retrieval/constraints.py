"""Hard-constraint evaluation (base.md §7.5, §9.4).

Each constraint evaluates per track to SATISFIED, VIOLATED or UNKNOWN, with the evidence used.
Only reliable catalog evidence decides. In the FMA-only MVP (ADR-0005) that means:

| Constraint | Decided by | Otherwise |
|---|---|---|
| vocals excluded / required | the curated FMA genre "Instrumental" | UNKNOWN (no vocal credits) |
| genre required / excluded | genre tags | UNKNOWN if the track has no genres |
| era / duration range | release year / duration | UNKNOWN if missing |
| instrument, tempo | nothing reliable (human labels only) | always UNKNOWN |

VIOLATED tracks are always excluded, whatever their score. UNKNOWN follows the configured
policy. If nothing survives, the caller reports NO_CONFIDENT_MATCH and never relaxes silently.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from music_discovery.domain.enums import ConstraintStatus
from music_discovery.domain.models import Track
from music_discovery.domain.schemas import (
    ConstraintAttribute,
    ConstraintOperator,
    ConstraintResult,
    HardConstraint,
)
from music_discovery.retrieval.config import ConstraintConfig

INSTRUMENTAL_GENRE = "instrumental"


def _words(text: str) -> set[str]:
    return set(text.casefold().replace("&", " and ").replace("-", " ").split())


def _genre_matches(value: str, genres: Sequence[str]) -> list[str]:
    """Genres containing every word of `value` ("electronic" matches "Ambient Electronic")."""
    wanted = _words(value)
    return [g for g in genres if wanted <= _words(g)]


def _result(
    constraint: HardConstraint, status: ConstraintStatus, *evidence: str
) -> ConstraintResult:
    return ConstraintResult(constraint=constraint, status=status, evidence=list(evidence))


def _vocals(constraint: HardConstraint, track: Track) -> ConstraintResult:
    instrumental = [g for g in track.genres if g.casefold() == INSTRUMENTAL_GENRE]
    if not instrumental:
        return _result(constraint, ConstraintStatus.UNKNOWN)
    evidence = f"genre tag '{instrumental[0]}' ({track.provenance.source})"
    if constraint.operator is ConstraintOperator.EXCLUDED:
        return _result(constraint, ConstraintStatus.SATISFIED, evidence)
    return _result(constraint, ConstraintStatus.VIOLATED, evidence)


def _genre(constraint: HardConstraint, track: Track) -> ConstraintResult:
    if not track.genres:
        return _result(constraint, ConstraintStatus.UNKNOWN)
    assert constraint.value is not None
    hits = _genre_matches(constraint.value, track.genres)
    source = track.provenance.source
    if constraint.operator is ConstraintOperator.REQUIRED:
        if hits:
            return _result(
                constraint, ConstraintStatus.SATISFIED, f"genre tag '{hits[0]}' ({source})"
            )
        return _result(constraint, ConstraintStatus.VIOLATED, f"genres {track.genres} ({source})")
    if hits:
        return _result(constraint, ConstraintStatus.VIOLATED, f"genre tag '{hits[0]}' ({source})")
    return _result(constraint, ConstraintStatus.SATISFIED, f"genres {track.genres} ({source})")


def _in_range(
    constraint: HardConstraint, value: float | None, label: str, track: Track
) -> ConstraintResult:
    if value is None:
        return _result(constraint, ConstraintStatus.UNKNOWN)
    assert constraint.range is not None
    low, high = constraint.range
    ok = (low is None or value >= low) and (high is None or value <= high)
    status = ConstraintStatus.SATISFIED if ok else ConstraintStatus.VIOLATED
    return _result(constraint, status, f"{label} {value:g} ({track.provenance.source})")


def evaluate(constraint: HardConstraint, track: Track) -> ConstraintResult:
    match constraint.attribute:
        case ConstraintAttribute.VOCALS:
            return _vocals(constraint, track)
        case ConstraintAttribute.GENRE:
            return _genre(constraint, track)
        case ConstraintAttribute.ERA:
            return _in_range(constraint, track.year, "year", track)
        case ConstraintAttribute.DURATION:
            return _in_range(constraint, track.duration_seconds, "duration (s)", track)
        case ConstraintAttribute.INSTRUMENT | ConstraintAttribute.TEMPO:
            # instrument presence and tempo have no reliable catalog evidence in the MVP;
            # audio similarity and estimated features never decide a hard constraint
            return _result(constraint, ConstraintStatus.UNKNOWN)


@dataclass
class ConstraintOutcome:
    kept: list[str]
    excluded: dict[str, list[ConstraintResult]] = field(default_factory=dict)
    results: dict[str, list[ConstraintResult]] = field(default_factory=dict)

    def unknown_count(self, track_id: str) -> int:
        return sum(r.status is ConstraintStatus.UNKNOWN for r in self.results.get(track_id, []))


def apply_constraints(
    track_ids: Sequence[str],
    tracks: Mapping[str, Track],
    constraints: Sequence[HardConstraint],
    policy: ConstraintConfig,
) -> ConstraintOutcome:
    if not constraints:
        return ConstraintOutcome(kept=list(track_ids), results={t: [] for t in track_ids})
    outcome = ConstraintOutcome(kept=[])
    for track_id in track_ids:
        track = tracks.get(track_id)
        results = (
            [evaluate(c, track) for c in constraints]
            if track is not None
            else [
                ConstraintResult(constraint=c, status=ConstraintStatus.UNKNOWN) for c in constraints
            ]
        )
        outcome.results[track_id] = results
        statuses = {r.status for r in results}
        if ConstraintStatus.VIOLATED in statuses or (
            policy.unknown == "exclude" and ConstraintStatus.UNKNOWN in statuses
        ):
            outcome.excluded[track_id] = results
        else:
            outcome.kept.append(track_id)
    return outcome


def describe(constraint: HardConstraint) -> str:
    if constraint.range is not None:
        low, high = ("" if bound is None else f"{bound:g}" for bound in constraint.range)
        return f"{constraint.attribute} in [{low}, {high}]"
    value = f" {constraint.value}" if constraint.value else ""
    return f"{constraint.attribute}{value} {constraint.operator}"


def no_confident_match_reasons(
    outcome: ConstraintOutcome, constraints: Sequence[HardConstraint]
) -> list[str]:
    """One line per constraint: how many candidates satisfied, violated or could not be checked."""
    reasons = []
    for i, constraint in enumerate(constraints):
        counts = dict.fromkeys(ConstraintStatus, 0)
        for results in outcome.results.values():
            counts[results[i].status] += 1
        satisfied = counts[ConstraintStatus.SATISFIED]
        violated = counts[ConstraintStatus.VIOLATED]
        unknown = counts[ConstraintStatus.UNKNOWN]
        reasons.append(
            f"{describe(constraint)}: {satisfied} satisfied, {violated} violated, {unknown} unknown"
        )
    return reasons
