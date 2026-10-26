"""Application results → public DTOs. Pure functions; nulls pass through as nulls."""

from __future__ import annotations

from music_discovery.api import schemas as s
from music_discovery.application.capabilities import Capabilities, SearchWarning
from music_discovery.application.feedback_service import FeedbackResult
from music_discovery.application.map_service import MapMeta, MapPage
from music_discovery.application.results import TrackView
from music_discovery.application.search_service import ResultItem, SearchResult
from music_discovery.application.track_service import NeighborsResult, TrackDetail
from music_discovery.domain.enums import CapabilityStatus
from music_discovery.domain.models import ArtistReference, SearchSession
from music_discovery.domain.schemas import SearchSpecification, WeightedPreference


def preview_url(view: TrackView) -> str | None:
    return f"/api/tracks/{view.track.id}/audio" if view.audio is not None else None


def artists(refs: list[ArtistReference]) -> list[s.Artist]:
    return [s.Artist(artist_id=a.artist_id, name=a.name) for a in refs]


def spatial(view: TrackView) -> s.Spatial | None:
    if view.coordinates is None or view.projection_version is None:
        return None
    x, y = view.coordinates
    return s.Spatial(x=x, y=y, projection_version=view.projection_version)


def capabilities(caps: Capabilities) -> s.Capabilities:
    return s.Capabilities(
        semantic=caps.semantic, llm_interpreter=caps.llm_interpreter, map=caps.map
    )


def warnings(items: list[SearchWarning]) -> list[s.ApiWarning]:
    return [s.ApiWarning(code=w.code, message=w.message) for w in items]


def _prefs(prefs: list[WeightedPreference]) -> list[s.Preference]:
    return [s.Preference(value=p.value, weight=p.weight, source_span=p.source_span) for p in prefs]


def interpreted_query(spec: SearchSpecification) -> s.InterpretedQuery:
    return s.InterpretedQuery(
        spec_version=spec.spec_version,
        original_query=spec.original_query,
        mood_preferences=_prefs(spec.mood_preferences),
        instrument_preferences=_prefs(spec.instrument_preferences),
        genre_preferences=_prefs(spec.genre_preferences),
        tempo_preferences=_prefs(spec.tempo_preferences),
        energy_preferences=_prefs(spec.energy_preferences),
        texture_preferences=_prefs(spec.texture_preferences),
        era_preferences=_prefs(spec.era_preferences),
        vocal_preferences=spec.vocal_preferences,
        hard_constraints=[
            s.HardConstraint(
                attribute=c.attribute, operator=c.operator, value=c.value, range=c.range
            )
            for c in spec.hard_constraints
        ],
        negative_preferences=_prefs(spec.negative_preferences),
        reference_track_ids=list(spec.reference_track_ids),
        negative_reference_track_ids=list(spec.negative_reference_track_ids),
        excluded_track_ids=list(spec.excluded_track_ids),
        semantic_prompts=list(spec.semantic_prompts),
        diversity=spec.diversity,
        uncertainties=list(spec.uncertainties),
        interpreter=spec.interpreter,
        interpreter_model=spec.interpreter_model,
    )


def track_result(item: ResultItem) -> s.TrackResult:
    candidate, view, track = item.candidate, item.view, item.view.track
    evidence = candidate.evidence
    return s.TrackResult(
        track_id=track.id,
        rank=candidate.rank,
        title=track.title,
        artists=artists(track.artists),
        score=candidate.score.final,
        score_breakdown=s.ScoreBreakdown(
            semantic=candidate.score.semantic,
            metadata=candidate.score.metadata,
            relationship=candidate.score.relationship,
            final=candidate.score.final,
        ),
        match_strength=None if evidence is None else evidence.score_bands.semantic,
        score_bands=s.ScoreBands(
            semantic=None if evidence is None else evidence.score_bands.semantic,
            metadata=None if evidence is None else evidence.score_bands.metadata,
            relationship=None if evidence is None else evidence.score_bands.relationship,
        ),
        description=None if item.explanation is None else item.explanation.description,
        match_reasons=[] if item.explanation is None else list(item.explanation.match_reasons),
        genres=list(track.genres),
        styles=list(track.styles),
        source_url=track.source_url,
        preview_url=preview_url(view),
        audio_available=track.audio_available,
        evidence_status=track.evidence_status,
        constraint_status=[
            s.ConstraintCheck(
                attribute=r.constraint.attribute,
                operator=r.constraint.operator,
                value=r.constraint.value,
                status=r.status,
            )
            for r in candidate.constraint_results
        ],
        uncertainty_flags=[] if evidence is None else list(evidence.uncertainty_flags),
        retrieval_sources=list(candidate.retrieval_sources),
        spatial=spatial(view),
    )


def search_response(result: SearchResult) -> s.SearchResponse:
    return s.SearchResponse(
        query_id=result.query_id,
        session_id=result.session.session_id,
        outcome=result.outcome.kind,
        clarification_question=result.outcome.clarification_question,
        no_match_reasons=list(result.outcome.reasons),
        interpreted_query=interpreted_query(result.spec),
        results=[track_result(item) for item in result.items],
        capabilities=capabilities(result.capabilities),
        warnings=warnings(result.warnings),
        change_summary=list(result.change_summary),
    )


def track_detail(detail: TrackDetail) -> s.TrackDetail:
    view, track = detail.view, detail.view.track
    release = detail.release
    return s.TrackDetail(
        track_id=track.id,
        title=track.title,
        artists=artists(track.artists),
        release=None
        if release is None
        else s.Release(release_id=release.id, title=release.title, year=release.year),
        year=track.year,
        genres=list(track.genres),
        styles=list(track.styles),
        tags=list(track.tags),
        duration_seconds=track.duration_seconds,
        source_url=track.source_url,
        preview_url=preview_url(view),
        audio_available=track.audio_available,
        evidence_status=track.evidence_status,
        audio=None
        if view.audio is None
        else s.AudioInfo(duration_seconds=view.audio.duration_seconds, license=view.audio.license),
        related_tracks=[
            s.RelatedTrack(
                track_id=r.view.track.id,
                title=r.view.track.title,
                artists=artists(r.view.track.artists),
                relationship_type=r.relationship.relationship_type,
            )
            for r in detail.related
        ],
        relationship_counts={str(k): v for k, v in detail.relationship_counts.items()},
        spatial=spatial(view),
    )


def neighbors_response(result: NeighborsResult) -> s.NeighborsResponse:
    return s.NeighborsResponse(
        track_id=result.track_id,
        metric=result.metric,
        model_id=result.model_id,
        reason=result.reason,
        neighbors=[
            s.Neighbor(
                track_id=i.view.track.id,
                title=i.view.track.title,
                artists=artists(i.view.track.artists),
                score=i.neighbor.score,
                relationship_types=list(i.neighbor.relationship_types),
                audio_available=i.view.track.audio_available,
                spatial=spatial(i.view),
            )
            for i in result.items
        ],
    )


def feedback_response(result: FeedbackResult) -> s.FeedbackResponse:
    return s.FeedbackResponse(
        accepted=result.accepted,
        reason=result.reason,
        updated_search_state=s.SearchState(
            session_id=result.session.session_id,
            session_version=result.session.version,
            interpreted_query=interpreted_query(result.spec),
        ),
        change_summary=list(result.change_summary),
        next_action=result.next_action,
        refreshed=None if result.refreshed is None else search_response(result.refreshed),
    )


def session_response(session: SearchSession) -> s.SessionResponse:
    return s.SessionResponse(
        session_id=session.session_id,
        created_at=session.created_at,
        version=session.version,
        original_query=session.original_query,
        turns=[
            s.SessionTurn(
                query_id=t.query_id,
                query_text=t.query_text,
                interpreted_query=interpreted_query(t.spec),
                result_track_ids=list(t.result_track_ids),
                created_at=t.created_at,
                triggered_by_event_id=t.triggered_by_event_id,
                change_summary=list(t.change_summary),
            )
            for t in session.turns
        ],
        feedback=[
            s.FeedbackEventRecord(
                event_id=e.event_id,
                query_id=e.query_id,
                event_type=e.event_type,
                track_id=e.track_id,
                attribute=e.attribute,
                value=e.value,
                free_text=e.free_text,
                timestamp=e.timestamp,
            )
            for e in session.feedback_history
        ],
    )


def map_points(page: MapPage) -> s.MapPointsResponse:
    if page.projection_version is None:
        raise ValueError("an unavailable map has no points response")
    return s.MapPointsResponse(
        points=[s.MapPoint(**p.model_dump()) for p in page.points],
        next_cursor=page.next_cursor,
        projection_version=page.projection_version,
    )


def map_meta(meta: MapMeta) -> s.MapMetaResponse:
    return s.MapMetaResponse(
        status=CapabilityStatus(meta.status),
        reason=meta.reason,
        projection_version=meta.projection_version,
        embedding_version=meta.embedding_version,
        model_id=meta.model_id,
        created_at=meta.created_at,
        bounds=None if meta.bounds is None else s.MapBounds(**meta.bounds.model_dump()),
        n_points=meta.n_points,
        excluded_tracks=meta.excluded_tracks,
        coordinate_transform=meta.coordinate_transform,
    )


def health(caps: Capabilities) -> s.HealthResponse:
    return s.HealthResponse(
        status="ok",
        api_version=s.API_VERSION,
        capabilities=capabilities(caps),
        semantic_reason=caps.semantic_reason,
        map_reason=caps.map_reason,
    )
