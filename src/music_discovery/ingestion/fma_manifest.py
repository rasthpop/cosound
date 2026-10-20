"""Deterministic draft of the 20-track FMA evaluation corpus (base.md §12.1).

At most one track per artist; among equally good candidates, uncovered top genres win.

Tracks are picked per query theme from metadata only: genres, title/tags and, where present,
echonest estimates. Metadata cannot prove how a track sounds, so every row is marked
`listening_status=pending` until a person has listened and confirmed or replaced it.
Ties are broken by a seeded hash, so the same inputs always give the same manifest.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from music_discovery.ingestion.fma_loader import FmaTrackRecord, fma_audio_path

MANIFEST_COLUMNS = (
    "fma_track_id",
    "title",
    "artist",
    "genre",
    "audio_path",
    "source",
    "license",
    "split",
    "theme",
    "selection_reason",
    "listening_status",
)
RESEARCH_LICENSE_MARKERS = ("attribution", "creative commons", "cc0", "public domain")


def license_permits_research(license_text: str | None) -> bool:
    if not license_text:
        return False
    lowered = license_text.casefold()
    return any(marker in lowered for marker in RESEARCH_LICENSE_MARKERS)


@dataclass(frozen=True)
class Candidate:
    record: FmaTrackRecord
    genres: frozenset[str]
    text: str
    echonest: Mapping[str, float]

    def has_genre(self, *names: str) -> bool:
        return any(n in self.genres for n in names)

    def feature(self, name: str) -> float | None:
        return self.echonest.get(name)


Predicate = Callable[[Candidate], bool]
Score = Callable[[Candidate], float]


@dataclass(frozen=True)
class Theme:
    key: str
    count: int
    reason: str
    predicate: Predicate
    score: Score


def _f(c: Candidate, name: str, default: float = 0.0) -> float:
    value = c.feature(name)
    return default if value is None else value


THEMES: tuple[Theme, ...] = (
    Theme(
        "flute",
        2,
        "title/tags mention flute or woodwind (query 1)",
        lambda c: "flute" in c.text or "woodwind" in c.text,
        lambda c: 1.0,
    ),
    Theme(
        "soft_piano",
        2,
        "title/tags mention piano; low echonest valence preferred (query 10)",
        lambda c: "piano" in c.text,
        lambda c: 1.0 - _f(c, "valence", 0.5),
    ),
    Theme(
        "calm_acoustic_instrumental",
        2,
        "echonest instrumentalness and acousticness >= 0.8, low energy (query 6)",
        lambda c: _f(c, "instrumentalness") >= 0.8 and _f(c, "acousticness") >= 0.8,
        lambda c: _f(c, "acousticness") + _f(c, "instrumentalness") - _f(c, "energy"),
    ),
    Theme(
        "jazz",
        2,
        "jazz genre or title/tags mention jazz (query 4)",
        lambda c: any("jazz" in g.casefold() for g in c.genres) or "jazz" in c.text,
        lambda c: 1.0 + _f(c, "acousticness"),
    ),
    Theme(
        "heavy_bass_electronic",
        2,
        "dubstep / drum & bass / trip-hop / dub genres (query 2)",
        lambda c: c.has_genre("Dubstep", "Drum & Bass", "Trip-Hop", "Reggae - Dub"),
        lambda c: _f(c, "energy", 0.5),
    ),
    Theme(
        "aggressive_fast",
        2,
        "punk / hardcore / metal genres, high energy and tempo (query 5)",
        lambda c: c.has_genre(
            "Punk", "Hardcore", "Metal", "Death-Metal", "Noise-Rock", "Loud-Rock"
        ),
        lambda c: _f(c, "energy", 0.5) + _f(c, "tempo", 120.0) / 200.0,
    ),
    Theme(
        "ambient_atmospheric",
        2,
        "ambient / drone / chill-out genres (query 7)",
        lambda c: c.has_genre("Ambient", "Ambient Electronic", "Drone", "Chill-out"),
        lambda c: 1.0 - _f(c, "energy", 0.5),
    ),
    Theme(
        "minimal_repetitive",
        1,
        "minimal electronic / minimalism / techno genres (query 9)",
        lambda c: c.has_genre("Minimal Electronic", "Minimalism", "Techno"),
        lambda c: 1.0,
    ),
    Theme(
        "playful_unusual",
        1,
        "glitch / chip / novelty / IDM / avant-garde genres (query 8)",
        lambda c: c.has_genre("Glitch", "Chip Music", "Novelty", "IDM", "Avant-Garde"),
        lambda c: _f(c, "danceability", 0.5),
    ),
    Theme(
        "vocal_candidate",
        2,
        "singer-songwriter / experimental pop / synth pop; vocals must be checked by ear (query 3)",
        lambda c: c.has_genre("Singer-Songwriter", "Experimental Pop", "Synth Pop"),
        lambda c: 1.0 - _f(c, "instrumentalness", 0.5),
    ),
    Theme(
        "negative_energetic_folk",
        1,
        "challenging negative: Folk like the flute picks, but high echonest energy",
        lambda c: (
            c.record.genre_top == "Folk"
            and _f(c, "energy") >= 0.7
            and "flute" not in c.text
            and "piano" not in c.text
        ),
        lambda c: _f(c, "energy"),
    ),
    Theme(
        "negative_speech_heavy",
        1,
        "challenging negative: Hip-Hop with high echonest speechiness (vs instrumental queries)",
        lambda c: c.record.genre_top == "Hip-Hop" and _f(c, "speechiness") >= 0.3,
        lambda c: _f(c, "speechiness"),
    ),
)


@dataclass(frozen=True)
class ManifestRow:
    record: FmaTrackRecord
    theme: str
    reason: str

    def as_csv(self, audio_dir_rel: Path) -> dict[str, str]:
        r = self.record
        return {
            "fma_track_id": str(r.fma_track_id),
            "title": r.title or "",
            "artist": r.artist_name or "",
            "genre": r.genre_top or "",
            "audio_path": fma_audio_path(audio_dir_rel, r.fma_track_id).as_posix(),
            "source": "fma_small",
            "license": r.license or "",
            "split": "corpus",
            "theme": self.theme,
            "selection_reason": self.reason,
            "listening_status": "pending",
        }


def _tiebreak(seed: int, fma_id: int) -> str:
    return hashlib.sha256(f"{seed}:{fma_id}".encode()).hexdigest()


def select_manifest(
    records: Sequence[FmaTrackRecord],
    *,
    genres: Mapping[int, str],
    echonest: Mapping[int, Mapping[str, float]],
    size: int = 20,
    seed: int = 42,
    themes: Sequence[Theme] = THEMES,
) -> list[ManifestRow]:
    pool = [
        Candidate(
            record=r,
            genres=frozenset(genres[g] for g in r.genre_all_ids if g in genres),
            text=" ".join([r.title or "", *r.tags]).casefold(),
            echonest=echonest.get(r.fma_track_id, {}),
        )
        for r in records
        if r.title and r.artist_name and license_permits_research(r.license)
    ]
    chosen: dict[int, ManifestRow] = {}
    artists: set[str] = set()

    def available(c: Candidate) -> bool:
        artist = (c.record.artist_name or "").casefold()
        return c.record.fma_track_id not in chosen and artist not in artists

    def take(c: Candidate, theme: str, reason: str) -> None:
        chosen[c.record.fma_track_id] = ManifestRow(c.record, theme, reason)
        artists.add((c.record.artist_name or "").casefold())

    for theme in themes:
        for _ in range(theme.count):
            covered = {row.record.genre_top for row in chosen.values()}
            ranked = sorted(
                (c for c in pool if theme.predicate(c) and available(c)),
                # strongest match first; among equals prefer a top genre not yet covered
                key=lambda c: (
                    -round(theme.score(c), 6),
                    c.record.genre_top in covered,
                    _tiebreak(seed, c.record.fma_track_id),
                ),
            )
            if not ranked:
                break
            take(ranked[0], theme.key, theme.reason)
        if len(chosen) >= size:
            break

    # Fill any shortfall with genre-coverage picks, least-covered top genre first.
    while len(chosen) < size:
        covered = {row.record.genre_top for row in chosen.values()}
        remaining = sorted(
            (c for c in pool if available(c)),
            key=lambda c: (c.record.genre_top in covered, _tiebreak(seed, c.record.fma_track_id)),
        )
        if not remaining:
            break
        pick = remaining[0]
        take(pick, "genre_coverage", f"fills genre coverage ({pick.record.genre_top})")
    return list(chosen.values())[:size]


def render_manifest(rows: Sequence[ManifestRow], *, audio_dir_rel: Path) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row.as_csv(audio_dir_rel))
    return buffer.getvalue()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
