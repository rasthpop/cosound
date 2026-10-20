"""Catalog relationship graph (base.md §10.3).

Edges are context for discovery and an optional ranking signal. They are not evidence that two
tracks sound alike. Every edge records the source of the data it was derived from.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from music_discovery.domain.enums import DataSource, RelationshipType
from music_discovery.domain.models import Track, TrackRelationship

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RelationshipConfig:
    max_group_size: int = 300
    """Groups larger than this (e.g. a huge label) are skipped to keep the graph bounded."""
    style_top_k: int = 10
    """Keep at most this many shared-style neighbors per track, strongest first."""
    min_style_weight: float = 0.2


def _evidence_source(a: Track, b: Track) -> DataSource:
    source = a.provenance.source
    return source if b.provenance.source is source else DataSource.DERIVED


def _group_edges(
    tracks: Sequence[Track],
    key: Callable[[Track], Iterable[str]],
    kind: RelationshipType,
    config: RelationshipConfig,
) -> list[TrackRelationship]:
    groups: dict[str, list[Track]] = defaultdict(list)
    for track in tracks:
        for value in dict.fromkeys(key(track)):
            groups[value].append(track)
    edges: dict[tuple[str, str], TrackRelationship] = {}
    for value, members in groups.items():
        if len(members) < 2:
            continue
        if len(members) > config.max_group_size:
            log.info("skipping large %s group %s (%d tracks)", kind, value, len(members))
            continue
        for a in members:
            for b in members:
                if a.id != b.id:
                    edges[(a.id, b.id)] = TrackRelationship(
                        source_track_id=a.id,
                        target_track_id=b.id,
                        relationship_type=kind,
                        evidence_source=_evidence_source(a, b),
                    )
    return list(edges.values())


def _style_edges(tracks: Sequence[Track], config: RelationshipConfig) -> list[TrackRelationship]:
    """Weighted by how rare the shared styles are (IDF-weighted overlap of style sets)."""
    styled = [t for t in tracks if t.styles]
    if len(styled) < 2:
        return []
    document_freq: dict[str, int] = defaultdict(int)
    for track in styled:
        for style in {s.casefold() for s in track.styles}:
            document_freq[style] += 1
    n = len(styled)
    idf = {s: math.log((n + 1) / (df + 1)) + 1.0 for s, df in document_freq.items()}
    by_style: dict[str, list[Track]] = defaultdict(list)
    for track in styled:
        for style in {s.casefold() for s in track.styles}:
            by_style[style].append(track)

    edges: list[TrackRelationship] = []
    for a in styled:
        a_styles = {s.casefold() for s in a.styles}
        candidates = {b.id: b for style in a_styles for b in by_style[style] if b.id != a.id}
        scored: list[tuple[float, str, Track]] = []
        for b in candidates.values():
            b_styles = {s.casefold() for s in b.styles}
            shared = sum(idf[s] for s in a_styles & b_styles)
            union = sum(idf[s] for s in a_styles | b_styles)
            weight = shared / union if union else 0.0
            if weight >= config.min_style_weight:
                scored.append((weight, b.id, b))
        scored.sort(key=lambda item: (-item[0], item[1]))
        for weight, _, b in scored[: config.style_top_k]:
            edges.append(
                TrackRelationship(
                    source_track_id=a.id,
                    target_track_id=b.id,
                    relationship_type=RelationshipType.SHARED_STYLE,
                    evidence_source=_evidence_source(a, b),
                    weight=round(weight, 6),
                )
            )
    return edges


def derive_relationships(
    tracks: Sequence[Track], config: RelationshipConfig | None = None
) -> list[TrackRelationship]:
    """All edges, both directions, sorted deterministically."""
    config = config or RelationshipConfig()
    edges = [
        *_group_edges(
            tracks, lambda t: [a.artist_id for a in t.artists], RelationshipType.SAME_ARTIST, config
        ),
        *_group_edges(
            tracks,
            lambda t: [lbl.label_id for lbl in t.labels],
            RelationshipType.SAME_LABEL,
            config,
        ),
        *_group_edges(
            tracks,
            lambda t: [t.master_release_id] if t.master_release_id else [],
            RelationshipType.SAME_MASTER,
            config,
        ),
        *_group_edges(
            tracks,
            lambda t: [t.release_id] if t.release_id else [],
            RelationshipType.SAME_RELEASE,
            config,
        ),
        *_style_edges(tracks, config),
    ]
    return sorted(
        edges, key=lambda r: (r.source_track_id, str(r.relationship_type), r.target_track_id)
    )
