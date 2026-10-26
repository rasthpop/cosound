// Friendly aliases over the generated OpenAPI types. No hand-written shapes that duplicate the
// schema live here: change the backend DTOs, then `make contract` and `npm run contract`.
// The only local type is `ApiError`, the client's normalized error (it also covers failures
// that never reached the server, so it is not part of the HTTP contract).
import type { components, operations } from "./generated";

type Schemas = components["schemas"];

// --- requests & responses ---------------------------------------------------------------
export type SearchRequest = Schemas["SearchRequest"];
export type SearchResponse = Schemas["SearchResponse"];
export type FeedbackRequest = Schemas["FeedbackRequest"];
export type FeedbackResponse = Schemas["FeedbackResponse"];
export type TrackDetail = Schemas["TrackDetail"];
export type NeighborsResponse = Schemas["NeighborsResponse"];
export type SessionResponse = Schemas["SessionResponse"];
export type MapPointsResponse = Schemas["MapPointsResponse"];
export type MapMeta = Schemas["MapMetaResponse"];
export type HealthResponse = Schemas["HealthResponse"];
export type ErrorResponse = Schemas["ErrorResponse"];

// --- parts ----------------------------------------------------------------------------------
export type TrackResult = Schemas["TrackResult"];
export type ScoreBreakdown = Schemas["ScoreBreakdown"];
export type ConstraintCheck = Schemas["ConstraintCheck"];
export type InterpretedQuery = Schemas["InterpretedQuery"];
export type Preference = Schemas["Preference"];
export type HardConstraint = Schemas["HardConstraint"];
export type Capabilities = Schemas["Capabilities"];
export type ApiWarning = Schemas["ApiWarning"];
export type Artist = Schemas["Artist"];
export type Spatial = Schemas["Spatial"];
export type Release = Schemas["Release"];
export type AudioInfo = Schemas["AudioInfo"];
export type RelatedTrack = Schemas["RelatedTrack"];
export type Neighbor = Schemas["Neighbor"];
export type SearchState = Schemas["SearchState"];
export type SessionTurn = Schemas["SessionTurn"];
export type FeedbackEventRecord = Schemas["FeedbackEventRecord"];
export type MapPoint = Schemas["MapPoint"];
export type MapBounds = Schemas["MapBounds"];
export type ErrorBody = Schemas["ErrorBody"];

// --- enums -----------------------------------------------------------------------------------
export type FeedbackType = Schemas["FeedbackType"];
export type NextAction = Schemas["NextAction"];
export type SearchOutcome = Schemas["SearchOutcomeKind"];
export type CapabilityStatus = Schemas["CapabilityStatus"];
export type InterpreterStatus = Schemas["InterpreterStatus"];
export type EvidenceStatus = Schemas["EvidenceStatus"];
export type ConstraintStatus = Schemas["ConstraintStatus"];
export type RelationshipType = Schemas["RelationshipType"];
export type RetrievalSource = Schemas["RetrievalSource"];
export type NeighborMetric = NeighborsResponse["metric"];

// --- query parameters -----------------------------------------------------------------------
export type MapPointsQuery = NonNullable<operations["getMapPoints"]["parameters"]["query"]>;
export type MapFilters = Pick<MapPointsQuery, "genre" | "style" | "artist_id" | "has_audio">;

// --- client errors ------------------------------------------------------------------------------
/** How a request failed: an error response, no response, cancelled, or an unreadable body. */
export type ApiErrorKind = "http" | "network" | "aborted" | "parse";

/** Every failure the API client reports. `code` is the server's stable code when there is one. */
export interface ApiError {
  kind: ApiErrorKind;
  code: string;
  message: string;
  /** HTTP status; `null` when no response arrived. */
  status: number | null;
  details: Record<string, unknown>;
}
