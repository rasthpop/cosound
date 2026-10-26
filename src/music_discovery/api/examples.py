"""Contract examples: one validated DTO per UI scenario (exported as frontend fixtures).

All tracks, artists and ids here are **fictional placeholders** ("Example …", `trk_example_…`)
that show the shape of each state; they are not catalog data and no link points anywhere real.
Every example is constructed through its DTO, so an invalid example fails at import.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache
from typing import Any

from pydantic import BaseModel

from music_discovery.api import schemas as s
from music_discovery.application.capabilities import WARNING_MESSAGES
from music_discovery.domain.enums import (
    CapabilityStatus,
    ConstraintStatus,
    EvidenceStatus,
    FeedbackType,
    InterpreterStatus,
    MatchStrength,
    NextAction,
    RelationshipType,
    RetrievalSource,
    SearchOutcomeKind,
)
from music_discovery.domain.schemas import ConstraintAttribute, ConstraintOperator

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
PROJECTION = "umap-example"
QUERY = "Something chill with a flute"

ALL_UP = s.Capabilities(
    semantic=CapabilityStatus.AVAILABLE,
    llm_interpreter=InterpreterStatus.DISABLED,
    map=CapabilityStatus.AVAILABLE,
)
SEMANTIC_DOWN = ALL_UP.model_copy(update={"semantic": CapabilityStatus.UNAVAILABLE})
MAP_DOWN = ALL_UP.model_copy(update={"map": CapabilityStatus.UNAVAILABLE})


def _artist(n: int) -> list[s.Artist]:
    return [s.Artist(artist_id=f"art_example_{n}", name=f"Example Artist {n}")]


def _query(**overrides: Any) -> s.InterpretedQuery:
    values: dict[str, Any] = {
        "spec_version": 1,
        "original_query": QUERY,
        "mood_preferences": [s.Preference(value="chill", weight=0.7, source_span="chill")],
        "instrument_preferences": [s.Preference(value="flute", weight=1.0, source_span="flute")],
        "genre_preferences": [],
        "tempo_preferences": [],
        "energy_preferences": [],
        "texture_preferences": [],
        "era_preferences": [],
        "vocal_preferences": "unspecified",
        "hard_constraints": [],
        "negative_preferences": [],
        "reference_track_ids": [],
        "negative_reference_track_ids": [],
        "excluded_track_ids": [],
        "semantic_prompts": ["chill music featuring flute"],
        "diversity": 0.5,
        "uncertainties": [],
        "interpreter": "deterministic",
        "interpreter_model": None,
    }
    values.update(overrides)
    return s.InterpretedQuery(**values)


def _band(value: float | None, strong: float, partial: float) -> MatchStrength | None:
    """Example bands, with the thresholds of config/descriptions.yaml (checked in tests)."""
    if value is None:
        return None
    if value >= strong:
        return MatchStrength.STRONG
    return MatchStrength.PARTIAL if value >= partial else MatchStrength.WEAK


def _result(n: int, *, semantic: bool = True, audio: bool = True) -> s.TrackResult:
    sem = round(0.9 - n * 0.08, 2) if semantic and audio else None
    meta = round(0.75 - n * 0.1, 2) if n < 3 else None
    final = round(max(v for v in (sem, meta, 0.05) if v is not None), 2)
    sources = [RetrievalSource.SEMANTIC] if sem is not None else []
    if meta is not None or not sources:
        sources.append(RetrievalSource.METADATA)
        meta = meta if meta is not None else 0.3
    strength = _band(sem, 0.8, 0.6)  # example ranks are <= strong_max_rank
    audio_reason = {
        MatchStrength.STRONG: "Strong audio match",
        MatchStrength.PARTIAL: "Partial audio match",
    }.get(strength or MatchStrength.WEAK)
    return s.TrackResult(
        track_id=f"trk_example_{n}",
        rank=n,
        title=f"Example Track {n}",
        artists=_artist(n),
        score=final,
        score_breakdown=s.ScoreBreakdown(
            semantic=sem, metadata=meta, relationship=None, final=final
        ),
        match_strength=strength,
        score_bands=s.ScoreBands(
            semantic=strength, metadata=_band(meta, 0.8, 0.3), relationship=None
        ),
        description=(
            "Its audio is a strong match for “chill music featuring flute”. Tagged Folk."
            if strength is MatchStrength.STRONG
            else "Its audio is a partial match for the requested sound. Tagged Folk."
            if strength is MatchStrength.PARTIAL
            else "Matched on metadata: Tagged Folk. Audio analysis unavailable."
        ),
        match_reasons=[r for r in (audio_reason, "Genre tag: Folk") if r is not None],
        genres=["Folk"],
        styles=[],
        source_url=None,
        preview_url=f"/api/tracks/trk_example_{n}/audio" if audio else None,
        audio_available=audio,
        evidence_status=(
            EvidenceStatus.AUDIO_AND_METADATA if audio else EvidenceStatus.METADATA_ONLY
        ),
        constraint_status=[],
        uncertainty_flags=[] if audio else ["no_audio"],
        retrieval_sources=sources,
        spatial=s.Spatial(x=round(-0.6 + n * 0.1, 2), y=0.25, projection_version=PROJECTION)
        if audio
        else None,
    )


def _search(**overrides: Any) -> s.SearchResponse:
    values: dict[str, Any] = {
        "query_id": "qry_example_1",
        "session_id": "ses_example_1",
        "outcome": SearchOutcomeKind.OK,
        "clarification_question": None,
        "no_match_reasons": [],
        "interpreted_query": _query(),
        "results": [_result(1), _result(2), _result(3, audio=False)],
        "capabilities": ALL_UP,
        "warnings": [],
        "change_summary": [],
    }
    values.update(overrides)
    return s.SearchResponse(**values)


def _error(code: str, message: str, **details: Any) -> s.ErrorResponse:
    return s.ErrorResponse(error=s.ErrorBody(code=code, message=message, details=details))


def _point(n: int) -> s.MapPoint:
    return s.MapPoint(
        track_id=f"trk_example_{n}",
        x=round(-1.0 + n * 0.4, 2),
        y=round(0.6 - n * 0.3, 2),
        title=f"Example Track {n}",
        artist=f"Example Artist {n}",
        genre="Folk" if n % 2 else "Electronic",
        style=None,
        source_url=None,
        has_audio=True,
    )


def _semantic_down_search() -> s.SearchResponse:
    return _search(
        results=[_result(1, semantic=False), _result(2, semantic=False)],
        capabilities=SEMANTIC_DOWN,
        warnings=[
            s.ApiWarning(
                code="semantic_unavailable",
                message=WARNING_MESSAGES["semantic_unavailable"],
            )
        ],
    )


@cache
def build_examples() -> dict[str, BaseModel]:
    """Fixture name → example DTO."""
    refined_query = _query(
        spec_version=2,
        excluded_track_ids=["trk_example_1"],
        genre_preferences=[s.Preference(value="electronic", weight=0.6, source_span=None)],
    )
    refined = _search(
        query_id="qry_example_2",
        interpreted_query=refined_query,
        results=[_result(1), _result(2)],
        change_summary=["excluded trk_example_1", "added electronic"],
    )
    return {
        "search_ok": _search(),
        "search_empty": _search(results=[]),
        "search_no_confident_match": _search(
            outcome=SearchOutcomeKind.NO_CONFIDENT_MATCH,
            results=[],
            no_match_reasons=["no track has reliable evidence for: vocals excluded"],
            interpreted_query=_query(
                original_query="instrumental only flute",
                vocal_preferences="excluded",
                hard_constraints=[
                    s.HardConstraint(
                        attribute=ConstraintAttribute.VOCALS, operator=ConstraintOperator.EXCLUDED
                    )
                ],
            ),
        ),
        "search_needs_clarification": _search(
            outcome=SearchOutcomeKind.NEEDS_CLARIFICATION,
            clarification_question="Should the music have vocals or not?",
            results=[],
            interpreted_query=_query(
                original_query="no vocals with female vocals",
                mood_preferences=[],
                instrument_preferences=[],
                semantic_prompts=[],
                uncertainties=["vocals are both excluded and requested"],
            ),
        ),
        "search_semantic_unavailable": _semantic_down_search(),
        "search_llm_fallback": _search(
            capabilities=ALL_UP.model_copy(update={"llm_interpreter": InterpreterStatus.FALLBACK}),
            warnings=[
                s.ApiWarning(
                    code="llm_fallback",
                    message=WARNING_MESSAGES["llm_fallback"],
                )
            ],
        ),
        "search_constraint_unknown": _search(
            results=[
                _result(1).model_copy(
                    update={
                        "constraint_status": [
                            s.ConstraintCheck(
                                attribute=ConstraintAttribute.VOCALS,
                                operator=ConstraintOperator.EXCLUDED,
                                value=None,
                                status=ConstraintStatus.UNKNOWN,
                            )
                        ],
                        "uncertainty_flags": ["vocals_unknown"],
                    }
                )
            ]
        ),
        "track_detail": s.TrackDetail(
            track_id="trk_example_1",
            title="Example Track 1",
            artists=_artist(1),
            release=s.Release(release_id="rel_example_1", title="Example Album", year=2012),
            year=2012,
            genres=["Folk"],
            styles=[],
            tags=["flute"],
            duration_seconds=212.0,
            source_url=None,
            preview_url="/api/tracks/trk_example_1/audio",
            audio_available=True,
            evidence_status=EvidenceStatus.AUDIO_AND_METADATA,
            audio=s.AudioInfo(duration_seconds=30.0, license="Example license"),
            related_tracks=[
                s.RelatedTrack(
                    track_id="trk_example_2",
                    title="Example Track 2",
                    artists=_artist(1),
                    relationship_type=RelationshipType.SAME_ARTIST,
                )
            ],
            relationship_counts={"same_artist": 1},
            spatial=s.Spatial(x=-0.5, y=0.25, projection_version=PROJECTION),
        ),
        "track_detail_no_audio": s.TrackDetail(
            track_id="trk_example_3",
            title="Example Track 3",
            artists=_artist(3),
            release=None,
            year=None,
            genres=["Folk"],
            styles=[],
            tags=[],
            duration_seconds=None,
            source_url=None,
            preview_url=None,
            audio_available=False,
            evidence_status=EvidenceStatus.METADATA_ONLY,
            audio=None,
            related_tracks=[],
            relationship_counts={},
            spatial=None,
        ),
        "neighbors": s.NeighborsResponse(
            track_id="trk_example_1",
            metric="clap_cosine",
            model_id="example-clap-model",
            reason=None,
            neighbors=[
                s.Neighbor(
                    track_id=f"trk_example_{n}",
                    title=f"Example Track {n}",
                    artists=_artist(n),
                    score=round(0.95 - n * 0.05, 2),
                    relationship_types=[],
                    audio_available=True,
                    spatial=s.Spatial(
                        x=round(-0.5 + n * 0.05, 2), y=0.3, projection_version=PROJECTION
                    ),
                )
                for n in (2, 4)
            ],
        ),
        "neighbors_no_audio": s.NeighborsResponse(
            track_id="trk_example_3",
            metric="catalog_relationship",
            model_id=None,
            reason="no_audio_embedding",
            neighbors=[
                s.Neighbor(
                    track_id="trk_example_5",
                    title="Example Track 5",
                    artists=_artist(3),
                    score=None,
                    relationship_types=[RelationshipType.SAME_ARTIST],
                    audio_available=False,
                    spatial=None,
                )
            ],
        ),
        "feedback_refined": s.FeedbackResponse(
            accepted=True,
            reason=None,
            updated_search_state=s.SearchState(
                session_id="ses_example_1", session_version=4, interpreted_query=refined_query
            ),
            change_summary=["excluded trk_example_1", "added electronic"],
            next_action=NextAction.REFINE_SEARCH,
            refreshed=refined,
        ),
        "feedback_rejected": s.FeedbackResponse(
            accepted=False,
            reason="nothing in the feedback text maps to a known attribute",
            updated_search_state=s.SearchState(
                session_id="ses_example_1", session_version=2, interpreted_query=_query()
            ),
            change_summary=[],
            next_action=NextAction.NONE,
            refreshed=None,
        ),
        "session": s.SessionResponse(
            session_id="ses_example_1",
            created_at=T0,
            version=4,
            original_query=QUERY,
            turns=[
                s.SessionTurn(
                    query_id="qry_example_1",
                    query_text=QUERY,
                    interpreted_query=_query(),
                    result_track_ids=["trk_example_1", "trk_example_2", "trk_example_3"],
                    created_at=T0,
                    triggered_by_event_id=None,
                    change_summary=[],
                ),
                s.SessionTurn(
                    query_id="qry_example_2",
                    query_text=QUERY,
                    interpreted_query=refined_query,
                    result_track_ids=["trk_example_1", "trk_example_2"],
                    created_at=T0,
                    triggered_by_event_id="evt_example_1",
                    change_summary=["excluded trk_example_1", "added electronic"],
                ),
            ],
            feedback=[
                s.FeedbackEventRecord(
                    event_id="evt_example_1",
                    query_id="qry_example_1",
                    event_type=FeedbackType.NOT_RELEVANT,
                    track_id="trk_example_1",
                    attribute=None,
                    value=None,
                    free_text=None,
                    timestamp=T0,
                )
            ],
        ),
        "map_points_page1": s.MapPointsResponse(
            points=[_point(n) for n in (1, 2, 3)],
            next_cursor="trk_example_3",
            projection_version=PROJECTION,
        ),
        "map_points_page2": s.MapPointsResponse(
            points=[_point(n) for n in (4, 5)], next_cursor=None, projection_version=PROJECTION
        ),
        "map_meta": s.MapMetaResponse(
            status=CapabilityStatus.AVAILABLE,
            reason=None,
            projection_version=PROJECTION,
            embedding_version="ev-example",
            model_id="example-clap-model",
            created_at=T0,
            bounds=s.MapBounds(min_x=-1.0, max_x=1.0, min_y=-0.9, max_y=0.9),
            n_points=5,
            excluded_tracks=1,
            coordinate_transform={"kind": "center_scale", "center": [0.0, 0.0], "scale": 1.0},
        ),
        "map_unavailable": s.MapMetaResponse(
            status=CapabilityStatus.UNAVAILABLE,
            reason="projection_unavailable",
            projection_version=None,
            embedding_version=None,
            model_id=None,
            created_at=None,
            bounds=None,
            n_points=0,
            excluded_tracks=None,
            coordinate_transform=None,
        ),
        "health": s.HealthResponse(
            status="ok",
            api_version=s.API_VERSION,
            capabilities=ALL_UP,
            semantic_reason=None,
            map_reason=None,
        ),
        "health_degraded": s.HealthResponse(
            status="ok",
            api_version=s.API_VERSION,
            capabilities=SEMANTIC_DOWN.model_copy(update={"map": CapabilityStatus.UNAVAILABLE}),
            semantic_reason="clap_checkpoint_missing",
            map_reason="projection_unavailable",
        ),
        "error_validation": _error(
            "validation_error",
            "Request is invalid.",
            errors=[{"loc": "body.query", "msg": "too short"}],
        ),
        "error_track_not_found": _error(
            "track_not_found", "Track trk_example_9 does not exist.", track_id="trk_example_9"
        ),
        "error_session_not_found": _error(
            "session_not_found", "Session ses_example_9 does not exist.", session_id="ses_example_9"
        ),
        "error_track_not_in_results": _error(
            "track_not_in_results",
            "Track trk_example_9 was not returned for query qry_example_1.",
            track_id="trk_example_9",
            query_id="qry_example_1",
        ),
        "error_map_unavailable": _error(
            "projection_unavailable", "The track map is not available."
        ),
        "error_audio_missing": _error(
            "audio_missing", "Track trk_example_3 has no validated audio.", track_id="trk_example_3"
        ),
        "error_internal": _error("internal_error", "Something went wrong."),
    }


def examples_for(cls: type[BaseModel]) -> list[dict[str, Any]]:
    return [m.model_dump(mode="json") for m in build_examples().values() if type(m) is cls]
