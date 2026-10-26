import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { fixtures } from "../mocks/fixtures";
import { server } from "../mocks/server";
import { ApiClientError, createApiClient, isAbortError, isApiError } from "./client";

const client = createApiClient({ baseUrl: "http://api.test" });

async function failure(promise: Promise<unknown>): Promise<ApiClientError> {
  try {
    await promise;
  } catch (error) {
    expect(isApiError(error)).toBe(true);
    return error as ApiClientError;
  }
  throw new Error("expected the call to fail");
}

describe("api client", () => {
  it("returns typed bodies on success", async () => {
    const plate = await client.search({ query: "chill flute", limit: 5 });
    expect(plate.outcome).toBe("ok");
    expect(plate.results[0]?.track_id).toBe("trk_example_1");
    const detail = await client.getTrack("trk_example_1");
    expect(detail.title).toBe(fixtures.track_detail.title);
  });

  it("sends JSON bodies and query parameters, skipping empty ones", async () => {
    let seen: { url: string; body: unknown } | null = null;
    server.use(
      http.post("http://api.test/api/feedback", async ({ request }) => {
        seen = { url: request.url, body: await request.json() };
        return HttpResponse.json(fixtures.feedback_rejected);
      }),
      http.get("http://api.test/api/map/points", ({ request }) => {
        seen = { url: request.url, body: null };
        return HttpResponse.json(fixtures.map_points_page2);
      }),
    );
    await client.submitFeedback({ session_id: "s", query_id: "q", free_text: "more piano" });
    expect(seen!.body).toEqual({ session_id: "s", query_id: "q", free_text: "more piano" });
    await client.getMapPoints({ limit: 2, genre: "Folk", cursor: null, has_audio: true });
    expect(seen!.url).toBe("http://api.test/api/map/points?limit=2&genre=Folk&has_audio=true");
  });

  it("encodes path segments", async () => {
    let url = "";
    server.use(
      http.get("http://api.test/api/tracks/:id", ({ request }) => {
        url = request.url;
        return HttpResponse.json(fixtures.track_detail);
      }),
    );
    await client.getTrack("a/b c");
    expect(url).toBe("http://api.test/api/tracks/a%2Fb%20c");
  });

  it("normalizes the error envelope", async () => {
    server.use(
      http.get("http://api.test/api/tracks/:id", () =>
        HttpResponse.json(fixtures.error_track_not_found, { status: 404 }),
      ),
    );
    const error = await failure(client.getTrack("trk_example_9"));
    expect(error.toJSON()).toEqual({
      kind: "http",
      code: "track_not_found",
      message: fixtures.error_track_not_found.error.message,
      status: 404,
      details: { track_id: "trk_example_9" },
    });
  });

  it("normalizes non-envelope error responses", async () => {
    server.use(http.get("http://api.test/api/health", () => new HttpResponse("Bad gateway", { status: 502 })));
    const error = await failure(client.health());
    expect([error.kind, error.code, error.status]).toEqual(["http", "http_502", 502]);
  });

  it("normalizes network failures", async () => {
    server.use(http.get("http://api.test/api/health", () => HttpResponse.error()));
    const error = await failure(client.health());
    expect([error.kind, error.code, error.status]).toEqual(["network", "network_error", null]);
  });

  it("normalizes aborts", async () => {
    const controller = new AbortController();
    const pending = client.getMapMeta({ signal: controller.signal });
    controller.abort();
    const error = await failure(pending);
    expect(error.kind).toBe("aborted");
    expect(isAbortError(error)).toBe(true);
  });

  it("normalizes malformed JSON", async () => {
    server.use(
      http.get(
        "http://api.test/api/map/meta",
        () => new HttpResponse("{not json", { headers: { "Content-Type": "application/json" } }),
      ),
    );
    const error = await failure(client.getMapMeta());
    expect([error.kind, error.code, error.status]).toEqual(["parse", "invalid_response", 200]);
  });

  it("resolves API paths such as preview urls", () => {
    expect(client.resolveUrl("/api/tracks/trk_1/audio")).toBe("http://api.test/api/tracks/trk_1/audio");
    expect(createApiClient({ baseUrl: "" }).resolveUrl("/api/health")).toBe(`${location.origin}/api/health`);
  });
});
