// MSW request handlers mirroring the HTTP contract, per scenario. Responses come from the
// contract fixtures; anything derived from them is built through the generated types, so it
// type-checks against api/types.ts. Mocks hold no ranking or retrieval logic: they replay
// fixtures, paginate a fixed point list and echo ids.
import { delay, http, HttpResponse, type HttpHandler, type JsonBodyType } from "msw";

import type {
  ErrorResponse,
  FeedbackRequest,
  FeedbackResponse,
  HealthResponse,
  MapMeta,
  MapPoint,
  MapPointsResponse,
  NeighborsResponse,
  SearchRequest,
  SearchResponse,
  SessionResponse,
  TrackDetail,
} from "../api/types";
import { fixture, type FixtureName } from "./fixtures";
import { generateMapPoints } from "./generateMapPoints";
import { SLOW_NETWORK_MS, type Scenario, type ScenarioOptions } from "./scenarios";

const API = "*/api";
const MAX_MAP_LIMIT = 5000;
const DEFAULT_MAP_LIMIT = 500;
const NO_AUDIO_TRACK = "trk_example_3";

/** The body is type-checked against `T`; MSW gets a plain Response (handlers mix bodies). */
const json = <T>(body: T, status = 200): Response =>
  HttpResponse.json(body as JsonBodyType, { status }) as Response;
const error = (name: FixtureName & `error_${string}`, status: number) =>
  json<ErrorResponse>(fixture(name) as ErrorResponse, status);

const SEARCH_FIXTURE: Partial<Record<Scenario, FixtureName>> = {
  "degraded-semantic": "search_semantic_unavailable",
  "no-confident-match": "search_no_confident_match",
  "needs-clarification": "search_needs_clarification",
};

/** Points the map serves: both fixture pages, or a synthetic set. */
function mapDataset(options: ScenarioOptions): MapPoint[] {
  if (options.mapPoints) {
    return generateMapPoints(options.mapPoints);
  }
  return [...fixture("map_points_page1").points, ...fixture("map_points_page2").points];
}

function mapDown(response: SearchResponse): SearchResponse {
  return {
    ...response,
    capabilities: { ...response.capabilities, map: "unavailable" },
    warnings: [
      ...response.warnings,
      { code: "map_unavailable", message: "The track map is unavailable; results have no map coordinates." },
    ],
    results: response.results.map((r) => ({ ...r, spatial: null })),
  };
}

export function handlersFor(scenario: Scenario, options: ScenarioOptions = {}): HttpHandler[] {
  const latency = options.latencyMs ?? (scenario === "slow-network" ? SLOW_NETWORK_MS : 0);
  const failing = scenario === "errors";
  const points = mapDataset(options);
  const projectionVersion = fixture("map_points_page1").projection_version;
  let queryCounter = 0;

  const wait = async () => {
    if (latency > 0) await delay(latency);
  };

  /** A search plate for this scenario, continuing `sessionId` when given. */
  const plate = (sessionId: string | null | undefined): SearchResponse => {
    const name = SEARCH_FIXTURE[scenario] ?? "search_ok";
    const base = fixture(name) as SearchResponse;
    queryCounter += 1;
    const response: SearchResponse = {
      ...base,
      session_id: sessionId ?? base.session_id,
      query_id: base.query_id === null ? null : `qry_mock_${queryCounter}`,
    };
    return scenario === "map-down" ? mapDown(response) : response;
  };

  return [
    http.get(`${API}/health`, async () => {
      await wait();
      if (failing) return error("error_internal", 500);
      const health = fixture("health") as HealthResponse;
      if (scenario === "degraded-semantic") {
        return json<HealthResponse>({
          ...health,
          capabilities: { ...health.capabilities, semantic: "unavailable" },
          semantic_reason: "clap_checkpoint_missing",
        });
      }
      if (scenario === "map-down") {
        return json<HealthResponse>({
          ...health,
          capabilities: { ...health.capabilities, map: "unavailable" },
          map_reason: "projection_unavailable",
        });
      }
      return json(health);
    }),

    http.post(`${API}/search`, async ({ request }) => {
      await wait();
      if (failing) return error("error_internal", 500);
      const body = (await request.json()) as Partial<SearchRequest>;
      const limit = body.limit ?? 10;
      if (typeof body.query !== "string" || !body.query.trim() || limit < 1 || limit > 100) {
        return error("error_validation", 422);
      }
      return json<SearchResponse>(plate(body.session_id));
    }),

    http.get(`${API}/tracks/:trackId`, async ({ params }) => {
      await wait();
      if (failing) return error("error_track_not_found", 404);
      const name = params.trackId === NO_AUDIO_TRACK ? "track_detail_no_audio" : "track_detail";
      const detail = fixture(name) as TrackDetail;
      return json<TrackDetail>({ ...detail, track_id: String(params.trackId) });
    }),

    http.get(`${API}/tracks/:trackId/neighbors`, async ({ params }) => {
      await wait();
      if (failing) return error("error_track_not_found", 404);
      const name = params.trackId === NO_AUDIO_TRACK ? "neighbors_no_audio" : "neighbors";
      const response = fixture(name) as NeighborsResponse;
      return json<NeighborsResponse>({ ...response, track_id: String(params.trackId) });
    }),

    http.get(`${API}/tracks/:trackId/audio`, async ({ params }) => {
      await wait();
      if (failing || params.trackId === NO_AUDIO_TRACK) return error("error_audio_missing", 404);
      return new Response(new Uint8Array(1024), {
        headers: { "Content-Type": "audio/mpeg", "X-Audio-License": "Example license" },
      });
    }),

    http.post(`${API}/feedback`, async ({ request }) => {
      await wait();
      if (failing) return error("error_track_not_in_results", 409);
      const body = (await request.json()) as FeedbackRequest;
      if (!body.event_type && body.free_text) {
        // free text the mock cannot map: the backend's "accepted: false" answer
        return json<FeedbackResponse>(fixture("feedback_rejected") as FeedbackResponse);
      }
      if (!body.event_type) return error("error_validation", 422);
      const refined = fixture("feedback_refined") as FeedbackResponse;
      return json<FeedbackResponse>({
        ...refined,
        updated_search_state: { ...refined.updated_search_state, session_id: body.session_id },
        // like the API, the refreshed plate reports what the feedback changed
        refreshed: body.refresh ? { ...plate(body.session_id), change_summary: refined.change_summary } : null,
      });
    }),

    http.get(`${API}/sessions/:sessionId`, async ({ params }) => {
      await wait();
      if (failing) return error("error_session_not_found", 404);
      const session = fixture("session") as SessionResponse;
      return json<SessionResponse>({ ...session, session_id: String(params.sessionId) });
    }),

    http.get(`${API}/map/meta`, async () => {
      await wait();
      if (failing) return error("error_internal", 500);
      if (scenario === "map-down") return json<MapMeta>(fixture("map_unavailable") as MapMeta);
      const meta = fixture("map_meta") as MapMeta;
      return json<MapMeta>({ ...meta, n_points: points.length });
    }),

    http.get(`${API}/map/points`, async ({ request }) => {
      await wait();
      if (failing) return error("error_internal", 500);
      if (scenario === "map-down") return error("error_map_unavailable", 503);
      const query = new URL(request.url).searchParams;
      const limit = Number(query.get("limit") ?? DEFAULT_MAP_LIMIT);
      if (!Number.isInteger(limit) || limit < 1 || limit > MAX_MAP_LIMIT) {
        return error("error_validation", 422);
      }
      const cursor = query.get("cursor");
      const genre = query.get("genre")?.toLowerCase();
      const style = query.get("style")?.toLowerCase();
      const hasAudio = query.get("has_audio");
      const matching = points.filter(
        (p) =>
          (cursor === null || p.track_id > cursor) &&
          (!genre || p.genre?.toLowerCase() === genre) &&
          (!style || p.style?.toLowerCase() === style) &&
          (hasAudio === null || String(p.has_audio) === hasAudio),
      );
      // artist_id filtering needs data map points do not carry; the mock ignores it
      const page = matching.slice(0, limit);
      const last = page.at(-1);
      return json<MapPointsResponse>({
        points: page,
        next_cursor: matching.length > limit && last ? last.track_id : null,
        projection_version: projectionVersion,
      });
    }),
  ];
}
