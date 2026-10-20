"""Conservative FMA <-> Discogs track matching (base.md §10.4).

A match is accepted only when title AND artist agree, at least one corroborating signal
(duration within tolerance, or the release/album title) agrees, and exactly one candidate
qualifies. Everything ambiguous stays UNRESOLVED with its candidates. Identifiers from the two
sources are never compared with each other; only names, titles and durations are.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from pydantic import JsonValue

from music_discovery.domain.enums import DataSource, ExternalIdKind, MatchStatus
from music_discovery.domain.ids import ExternalId
from music_discovery.domain.models import CrossSourceMatch, Track
from music_discovery.ingestion.names import matching_key

METHOD = "title_artist_corroborated_v1"


@dataclass(frozen=True)
class MatchConfig:
    duration_tolerance_s: float = 3.0


@dataclass(frozen=True)
class _Signals:
    candidate: Track
    title: bool
    artist: bool
    duration_delta_s: float | None
    release_title: bool
    year: bool | None

    def duration_ok(self, config: MatchConfig) -> bool:
        return (
            self.duration_delta_s is not None
            and self.duration_delta_s <= config.duration_tolerance_s
        )

    def duration_contradicts(self, config: MatchConfig) -> bool:
        return (
            self.duration_delta_s is not None
            and self.duration_delta_s > config.duration_tolerance_s
        )

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "title": self.title,
            "artist": self.artist,
            "duration_delta_s": self.duration_delta_s,
            "release_title": self.release_title,
            "year": self.year,
        }


def _artist_keys(track: Track) -> set[str]:
    return {matching_key(a.name) for a in track.artists if matching_key(a.name)}


def _discogs_track_ext(track: Track) -> ExternalId | None:
    return next(
        (
            e
            for e in track.external_ids
            if e.source is DataSource.DISCOGS and e.kind is ExternalIdKind.TRACK
        ),
        None,
    )


class SourceMatcher:
    def __init__(
        self,
        discogs_tracks: Sequence[Track],
        *,
        release_titles: Mapping[str, str],
        config: MatchConfig | None = None,
    ) -> None:
        """`release_titles` maps internal release ids to titles, for both sources."""
        self._config = config or MatchConfig()
        self._release_titles = {k: matching_key(v) for k, v in release_titles.items()}
        self._by_artist: dict[str, list[Track]] = defaultdict(list)
        for track in discogs_tracks:
            if _discogs_track_ext(track) is None:
                continue
            for key in _artist_keys(track):
                self._by_artist[key].append(track)

    def _signals(self, fma: Track, candidate: Track) -> _Signals:
        delta = None
        if fma.duration_seconds is not None and candidate.duration_seconds is not None:
            delta = round(abs(fma.duration_seconds - candidate.duration_seconds), 3)
        fma_release = self._release_titles.get(fma.release_id or "")
        cand_release = self._release_titles.get(candidate.release_id or "")
        year = None if fma.year is None or candidate.year is None else fma.year == candidate.year
        return _Signals(
            candidate=candidate,
            title=matching_key(fma.title) == matching_key(candidate.title),
            artist=bool(_artist_keys(fma) & _artist_keys(candidate)),
            duration_delta_s=delta,
            release_title=bool(fma_release and fma_release == cand_release),
            year=year,
        )

    def match(self, fma: Track, *, decided_at: datetime) -> CrossSourceMatch | None:
        """Decision for one FMA track, or None when no candidate shares title and artist."""
        pool = {t.id: t for key in _artist_keys(fma) for t in self._by_artist.get(key, [])}
        signals = [self._signals(fma, c) for c in sorted(pool.values(), key=lambda t: t.id)]
        plausible = [s for s in signals if s.title and s.artist]
        if not plausible:
            return None
        cfg = self._config
        consistent = [s for s in plausible if not s.duration_contradicts(cfg)]
        corroborated = [s for s in consistent if s.duration_ok(cfg) or s.release_title]
        candidates = [e for s in plausible if (e := _discogs_track_ext(s.candidate)) is not None]

        if len(corroborated) == 1:
            best = corroborated[0]
            status = MatchStatus.ACCEPTED
            confidence = min(
                0.99,
                0.7
                + (0.15 if best.duration_ok(cfg) else 0.0)
                + (0.1 if best.release_title else 0.0)
                + (0.04 if best.year else 0.0),
            )
        elif not consistent:
            best = plausible[0]
            status = MatchStatus.REJECTED
            confidence = None
        else:
            best = (corroborated or consistent)[0]
            status = MatchStatus.UNRESOLVED
            confidence = None

        target = _discogs_track_ext(best.candidate)
        assert target is not None
        return CrossSourceMatch.model_validate(
            {
                "track_id": fma.id,
                "target": target,
                "target_position": target.value.split(":", 1)[1] if ":" in target.value else None,
                "status": status,
                "method": METHOD,
                "confidence": round(confidence, 3) if confidence is not None else None,
                "signals": {
                    "chosen": best.as_json(),
                    "plausible_candidates": len(plausible),
                    "corroborated_candidates": len(corroborated),
                },
                "candidates": candidates if status is not MatchStatus.ACCEPTED else [target],
                "decided_at": decided_at,
            }
        )
