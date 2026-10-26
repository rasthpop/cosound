// Typed access to the contract fixtures exported by scripts/export_fixtures.py.
//
// JSON imports are typed structurally by TypeScript (enum strings widen to `string`), so each
// fixture is bound to its DTO type here. That binding is safe because the backend test suite
// validates every fixture against the same DTO the generated types come from, and
// fixtures.test.ts checks this table against fixtures/index.json (the backend's own mapping).
import type {
  ErrorResponse,
  FeedbackResponse,
  HealthResponse,
  MapMeta,
  MapPointsResponse,
  NeighborsResponse,
  SearchResponse,
  SessionResponse,
  TrackDetail,
} from "../api/types";
import errorAudioMissing from "./fixtures/error_audio_missing.json";
import errorInternal from "./fixtures/error_internal.json";
import errorMapUnavailable from "./fixtures/error_map_unavailable.json";
import errorSessionNotFound from "./fixtures/error_session_not_found.json";
import errorTrackNotFound from "./fixtures/error_track_not_found.json";
import errorTrackNotInResults from "./fixtures/error_track_not_in_results.json";
import errorValidation from "./fixtures/error_validation.json";
import feedbackRefined from "./fixtures/feedback_refined.json";
import feedbackRejected from "./fixtures/feedback_rejected.json";
import health from "./fixtures/health.json";
import healthDegraded from "./fixtures/health_degraded.json";
import mapMeta from "./fixtures/map_meta.json";
import mapPointsPage1 from "./fixtures/map_points_page1.json";
import mapPointsPage2 from "./fixtures/map_points_page2.json";
import mapUnavailable from "./fixtures/map_unavailable.json";
import neighbors from "./fixtures/neighbors.json";
import neighborsNoAudio from "./fixtures/neighbors_no_audio.json";
import searchConstraintUnknown from "./fixtures/search_constraint_unknown.json";
import searchEmpty from "./fixtures/search_empty.json";
import searchLlmFallback from "./fixtures/search_llm_fallback.json";
import searchNeedsClarification from "./fixtures/search_needs_clarification.json";
import searchNoConfidentMatch from "./fixtures/search_no_confident_match.json";
import searchOk from "./fixtures/search_ok.json";
import searchSemanticUnavailable from "./fixtures/search_semantic_unavailable.json";
import session from "./fixtures/session.json";
import trackDetail from "./fixtures/track_detail.json";
import trackDetailNoAudio from "./fixtures/track_detail_no_audio.json";

const as = <T>(value: unknown): T => value as T;

export const fixtures = {
  error_audio_missing: as<ErrorResponse>(errorAudioMissing),
  error_internal: as<ErrorResponse>(errorInternal),
  error_map_unavailable: as<ErrorResponse>(errorMapUnavailable),
  error_session_not_found: as<ErrorResponse>(errorSessionNotFound),
  error_track_not_found: as<ErrorResponse>(errorTrackNotFound),
  error_track_not_in_results: as<ErrorResponse>(errorTrackNotInResults),
  error_validation: as<ErrorResponse>(errorValidation),
  feedback_refined: as<FeedbackResponse>(feedbackRefined),
  feedback_rejected: as<FeedbackResponse>(feedbackRejected),
  health: as<HealthResponse>(health),
  health_degraded: as<HealthResponse>(healthDegraded),
  map_meta: as<MapMeta>(mapMeta),
  map_points_page1: as<MapPointsResponse>(mapPointsPage1),
  map_points_page2: as<MapPointsResponse>(mapPointsPage2),
  map_unavailable: as<MapMeta>(mapUnavailable),
  neighbors: as<NeighborsResponse>(neighbors),
  neighbors_no_audio: as<NeighborsResponse>(neighborsNoAudio),
  search_constraint_unknown: as<SearchResponse>(searchConstraintUnknown),
  search_empty: as<SearchResponse>(searchEmpty),
  search_llm_fallback: as<SearchResponse>(searchLlmFallback),
  search_needs_clarification: as<SearchResponse>(searchNeedsClarification),
  search_no_confident_match: as<SearchResponse>(searchNoConfidentMatch),
  search_ok: as<SearchResponse>(searchOk),
  search_semantic_unavailable: as<SearchResponse>(searchSemanticUnavailable),
  session: as<SessionResponse>(session),
  track_detail: as<TrackDetail>(trackDetail),
  track_detail_no_audio: as<TrackDetail>(trackDetailNoAudio),
};

export type FixtureName = keyof typeof fixtures;

/** The DTO each fixture is typed as (checked against fixtures/index.json in tests). */
export const fixtureSchemas: Record<FixtureName, string> = {
  error_audio_missing: "ErrorResponse",
  error_internal: "ErrorResponse",
  error_map_unavailable: "ErrorResponse",
  error_session_not_found: "ErrorResponse",
  error_track_not_found: "ErrorResponse",
  error_track_not_in_results: "ErrorResponse",
  error_validation: "ErrorResponse",
  feedback_refined: "FeedbackResponse",
  feedback_rejected: "FeedbackResponse",
  health: "HealthResponse",
  health_degraded: "HealthResponse",
  map_meta: "MapMetaResponse",
  map_points_page1: "MapPointsResponse",
  map_points_page2: "MapPointsResponse",
  map_unavailable: "MapMetaResponse",
  neighbors: "NeighborsResponse",
  neighbors_no_audio: "NeighborsResponse",
  search_constraint_unknown: "SearchResponse",
  search_empty: "SearchResponse",
  search_llm_fallback: "SearchResponse",
  search_needs_clarification: "SearchResponse",
  search_no_confident_match: "SearchResponse",
  search_ok: "SearchResponse",
  search_semantic_unavailable: "SearchResponse",
  session: "SessionResponse",
  track_detail: "TrackDetail",
  track_detail_no_audio: "TrackDetail",
};

/** A deep copy, so handlers can adjust a fixture without changing the shared one. */
export function fixture<N extends FixtureName>(name: N): (typeof fixtures)[N] {
  return structuredClone(fixtures[name]);
}
