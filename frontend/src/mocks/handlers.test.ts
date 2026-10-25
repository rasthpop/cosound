import { describe, expect, it } from "vitest";

import type { MapPointsResponse, SearchResponse } from "../api/types";
import { fixtureSchemas, fixtures } from "./fixtures";
import index from "./fixtures/index.json";
import { generateMapPoints } from "./generateMapPoints";
import { handlersFor } from "./handlers";
import { SCENARIOS, scenarioFromQuery, type Scenario } from "./scenarios";
import { server } from "./server";

const BASE = "http://localhost/api";

function use(scenario: Scenario, options = {}) {
  server.use(...handlersFor(scenario, options));
}

async function post<T>(path: string, body: unknown): Promise<{ status: number; body: T }> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: (await res.json()) as T };
}

async function get<T>(path: string): Promise<{ status: number; body: T }> {
  const res = await fetch(`${BASE}${path}`);
  return { status: res.status, body: (await res.json()) as T };
}

describe("fixtures", () => {
  it("bind every exported fixture to the DTO the backend declares", () => {
    expect(fixtureSchemas).toEqual(index);
    expect(Object.keys(fixtures).sort()).toEqual(Object.keys(index).sort());
  });
});

describe("scenarios", () => {
  it("parse from the query string with safe defaults", () => {
    expect(scenarioFromQuery("?scenario=map-down")).toEqual({ scenario: "map-down", options: {} });
    expect(scenarioFromQuery("?scenario=nope&mapPoints=10000")).toEqual({
      scenario: "happy",
      options: { mapPoints: 10000 },
    });
    expect(scenarioFromQuery("").scenario).toBe("happy");
  });

  it.each(SCENARIOS.filter((s) => s !== "slow-network"))("%s answers every endpoint", async (s) => {
    use(s);
    const paths = ["/health", "/tracks/trk_example_1", "/tracks/trk_example_1/neighbors", "/sessions/ses_x", "/map/meta", "/map/points"];
    for (const path of paths) {
      const res = await fetch(`${BASE}${path}`);
      expect(res.status, `${s} ${path}`).toBeLessThan(600);
      expect(await res.json()).toBeTypeOf("object");
    }
    const search = await post<SearchResponse>("/search", { query: "chill flute" });
    expect([200, 500]).toContain(search.status);
  });
});

describe("happy", () => {
  it("search echoes the session and issues new query ids", async () => {
    const first = await post<SearchResponse>("/search", { query: "chill flute" });
    expect(first.status).toBe(200);
    expect(first.body.outcome).toBe("ok");
    const second = await post<SearchResponse>("/search", { query: "more", session_id: "ses_mine" });
    expect(second.body.session_id).toBe("ses_mine");
    expect(second.body.query_id).not.toBe(first.body.query_id);
  });

  it("rejects invalid search input with the validation envelope", async () => {
    const res = await post<{ error: { code: string } }>("/search", { query: "  " });
    expect(res.status).toBe(422);
    expect(res.body.error.code).toBe("validation_error");
  });

  it("feedback refreshes only when asked and rejects unmappable free text", async () => {
    const refreshed = await post<{ refreshed: SearchResponse | null }>("/feedback", {
      session_id: "ses_mine",
      query_id: "qry_1",
      event_type: "NOT_RELEVANT",
      track_id: "trk_example_1",
      refresh: true,
    });
    expect(refreshed.body.refreshed?.session_id).toBe("ses_mine");
    const plain = await post<{ refreshed: unknown }>("/feedback", {
      session_id: "ses_mine",
      query_id: "qry_1",
      event_type: "NOT_RELEVANT",
      track_id: "trk_example_1",
    });
    expect(plain.body.refreshed).toBeNull();
    const rejected = await post<{ accepted: boolean }>("/feedback", {
      session_id: "ses_mine",
      query_id: "qry_1",
      free_text: "lovely weather",
    });
    expect(rejected.body.accepted).toBe(false);
  });

  it("track without audio gets the no-audio fixtures", async () => {
    expect((await get<{ audio: unknown }>("/tracks/trk_example_3")).body.audio).toBeNull();
    const audio = await fetch(`${BASE}/tracks/trk_example_3/audio`);
    expect(audio.status).toBe(404);
  });

  it("map pages reproduce the fixture pages", async () => {
    const page1 = await get<MapPointsResponse>("/map/points?limit=3");
    expect(page1.body).toEqual(fixtures.map_points_page1);
    const page2 = await get<MapPointsResponse>(`/map/points?limit=3&cursor=${page1.body.next_cursor}`);
    expect(page2.body).toEqual(fixtures.map_points_page2);
  });

  it("map limit is bounded", async () => {
    expect((await fetch(`${BASE}/map/points?limit=5001`)).status).toBe(422);
  });
});

describe("degraded scenarios", () => {
  it("map-down: points 503, meta unavailable, search still answers without coordinates", async () => {
    use("map-down");
    expect((await fetch(`${BASE}/map/points`)).status).toBe(503);
    expect((await get<{ status: string }>("/map/meta")).body.status).toBe("unavailable");
    const search = await post<SearchResponse>("/search", { query: "x" });
    expect(search.status).toBe(200);
    expect(search.body.capabilities.map).toBe("unavailable");
    expect(search.body.results.every((r) => r.spatial === null)).toBe(true);
  });

  it.each([
    ["degraded-semantic", "ok"],
    ["no-confident-match", "no_confident_match"],
    ["needs-clarification", "needs_clarification"],
  ] as const)("%s search outcome is %s", async (scenario, outcome) => {
    use(scenario);
    expect((await post<SearchResponse>("/search", { query: "x" })).body.outcome).toBe(outcome);
  });

  it("errors: envelopes with matching statuses", async () => {
    use("errors");
    const search = await post<{ error: { code: string } }>("/search", { query: "x" });
    expect([search.status, search.body.error.code]).toEqual([500, "internal_error"]);
    const track = await get<{ error: { code: string } }>("/tracks/trk_example_1");
    expect([track.status, track.body.error.code]).toEqual([404, "track_not_found"]);
  });

  it("slow-network delays responses", async () => {
    use("happy", { latencyMs: 60 });
    const started = performance.now();
    await fetch(`${BASE}/health`);
    expect(performance.now() - started).toBeGreaterThanOrEqual(50);
  });
});

describe("synthetic map points", () => {
  it("are deterministic, sorted, bounded and paginate completely", async () => {
    const points = generateMapPoints(25);
    expect(generateMapPoints(25)).toEqual(points);
    expect(points.map((p) => p.track_id)).toEqual([...points.map((p) => p.track_id)].sort());
    expect(points.every((p) => Math.abs(p.x) <= 1 && Math.abs(p.y) <= 1)).toBe(true);

    use("happy", { mapPoints: 25 });
    const seen: string[] = [];
    let cursor: string | null = null;
    do {
      const query: string = cursor ? `&cursor=${cursor}` : "";
      const page: MapPointsResponse = (await get<MapPointsResponse>(`/map/points?limit=10${query}`)).body;
      seen.push(...page.points.map((p) => p.track_id));
      cursor = page.next_cursor;
    } while (cursor);
    expect(seen).toEqual(points.map((p) => p.track_id));
  });
});

describe("unhandled requests", () => {
  it("fail instead of reaching a real backend", async () => {
    await expect(fetch(`${BASE}/not-an-endpoint`)).rejects.toThrow();
  });
});
