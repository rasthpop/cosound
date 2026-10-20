from music_discovery.domain.enums import DataSource, RelationshipType
from music_discovery.domain.models import ArtistReference, LabelReference, Provenance, Track
from music_discovery.ingestion.relationships import RelationshipConfig, derive_relationships

DISCOGS = Provenance(source=DataSource.DISCOGS)
FMA = Provenance(source=DataSource.FMA)


def track(track_id: str, **kw: object) -> Track:
    values: dict[str, object] = {"id": track_id, "title": track_id, "provenance": DISCOGS}
    values.update(kw)
    return Track.model_validate(values)


ART = [ArtistReference(artist_id="art_1", name="A")]
LBL = [LabelReference(label_id="lbl_1", name="L")]

CATALOG = [
    track(
        "trk_a",
        artists=ART,
        labels=LBL,
        release_id="rel_1",
        master_release_id="mst_1",
        styles=["Ambient", "Downtempo"],
    ),
    track("trk_b", artists=ART, release_id="rel_1", master_release_id="mst_1", styles=["Ambient"]),
    track(
        "trk_c",
        labels=LBL,
        release_id="rel_2",
        master_release_id="mst_1",
        styles=["Downtempo", "Dub"],
    ),
    track("trk_d", styles=["Hardcore"], provenance=FMA),
    track("trk_e", artists=ART, provenance=FMA),
]


def edges_of(kind: RelationshipType) -> set[tuple[str, str]]:
    return {
        (e.source_track_id, e.target_track_id)
        for e in derive_relationships(CATALOG)
        if e.relationship_type is kind
    }


def test_group_relationships_are_symmetric() -> None:
    assert edges_of(RelationshipType.SAME_ARTIST) == {
        (a, b) for a in ("trk_a", "trk_b", "trk_e") for b in ("trk_a", "trk_b", "trk_e") if a != b
    }
    assert edges_of(RelationshipType.SAME_LABEL) == {("trk_a", "trk_c"), ("trk_c", "trk_a")}
    assert edges_of(RelationshipType.SAME_RELEASE) == {("trk_a", "trk_b"), ("trk_b", "trk_a")}
    assert len(edges_of(RelationshipType.SAME_MASTER)) == 6


def test_shared_style_weights_reward_rare_overlap() -> None:
    style = {
        (e.source_track_id, e.target_track_id): e.weight
        for e in derive_relationships(CATALOG)
        if e.relationship_type is RelationshipType.SHARED_STYLE
    }
    assert ("trk_d", "trk_a") not in style, "no shared style, no edge"
    assert style[("trk_a", "trk_b")] is not None
    assert 0 < style[("trk_a", "trk_b")] <= 1  # type: ignore[operator]
    assert all(w is not None and 0 < w <= 1 for w in style.values())


def test_every_edge_has_evidence_source() -> None:
    edges = derive_relationships(CATALOG)
    mixed = next(e for e in edges if {e.source_track_id, e.target_track_id} == {"trk_a", "trk_e"})
    assert mixed.evidence_source is DataSource.DERIVED
    same = next(e for e in edges if (e.source_track_id, e.target_track_id) == ("trk_a", "trk_b"))
    assert same.evidence_source is DataSource.DISCOGS
    assert all(e.source_track_id != e.target_track_id for e in edges)


def test_deterministic_and_bounded() -> None:
    assert derive_relationships(CATALOG) == derive_relationships(list(reversed(CATALOG)))
    tight = RelationshipConfig(max_group_size=2, style_top_k=1)
    edges = derive_relationships(CATALOG, tight)
    assert not any(e.relationship_type is RelationshipType.SAME_ARTIST for e in edges), (
        "group of 3 skipped"
    )
    per_track: dict[str, int] = {}
    for e in edges:
        if e.relationship_type is RelationshipType.SHARED_STYLE:
            per_track[e.source_track_id] = per_track.get(e.source_track_id, 0) + 1
    assert max(per_track.values()) == 1


def test_empty_catalog() -> None:
    assert derive_relationships([]) == []
