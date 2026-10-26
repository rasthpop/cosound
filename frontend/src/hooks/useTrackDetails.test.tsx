import { act, renderHook, waitFor } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import { fixtures } from "../mocks/fixtures";
import { server } from "../mocks/server";
import { useTrackDetails, type UseTrackDetailsOptions } from "./useTrackDetails";

const BASE = "http://api.test";
const client = createApiClient({ baseUrl: BASE });

/** Counts requests per path while answering from the happy-path handlers. */
function countRequests() {
  const counts: Record<string, number> = {};
  server.events.on("request:start", ({ request }) => {
    const path = new URL(request.url).pathname;
    counts[path] = (counts[path] ?? 0) + 1;
  });
  return counts;
}

function render(initial: string | null, options: UseTrackDetailsOptions = {}) {
  return renderHook(({ id, opts }) => useTrackDetails(id, { client, ...opts }), {
    initialProps: { id: initial, opts: options },
  });
}

describe("useTrackDetails", () => {
  it("is idle without an id and loads details by id", async () => {
    const { result, rerender } = render(null);
    expect(result.current.status).toBe("idle");
    rerender({ id: "trk_example_1", opts: {} });
    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.detail?.track_id).toBe("trk_example_1");
    expect(result.current.neighbors).toBeNull();
  });

  it("fetches neighbors when asked", async () => {
    const { result } = render("trk_example_1", { withNeighbors: true, k: 2 });
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.neighbors?.metric).toBe("clap_cosine");
  });

  it("serves a cache hit without a request", async () => {
    const counts = countRequests();
    const { result, rerender } = render("trk_example_1");
    await waitFor(() => expect(result.current.status).toBe("success"));
    rerender({ id: "trk_example_2", opts: {} });
    await waitFor(() => expect(result.current.detail?.track_id).toBe("trk_example_2"));
    rerender({ id: "trk_example_1", opts: {} });
    expect(result.current.status).toBe("success"); // immediately, from the cache
    expect(result.current.detail?.track_id).toBe("trk_example_1");
    expect(counts["/api/tracks/trk_example_1"]).toBe(1);
    server.events.removeAllListeners();
  });

  it("drops the cache when the projection version changes", async () => {
    const counts = countRequests();
    const { result, rerender } = render("trk_example_1", { projectionVersion: "umap-a" });
    await waitFor(() => expect(result.current.status).toBe("success"));
    rerender({ id: "trk_example_1", opts: { projectionVersion: "umap-b" } });
    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(counts["/api/tracks/trk_example_1"]).toBe(2);
    server.events.removeAllListeners();
  });

  it("aborts the previous request when the id changes", async () => {
    const signals = new Map<string, AbortSignal>();
    server.use(
      http.get(`${BASE}/api/tracks/:id`, async ({ params, request }) => {
        signals.set(String(params.id), request.signal);
        await delay(params.id === "trk_slow" ? "infinite" : 5);
        return HttpResponse.json({ ...fixtures.track_detail, track_id: String(params.id) });
      }),
    );
    const { result, rerender } = render("trk_slow");
    await waitFor(() => expect(signals.has("trk_slow")).toBe(true));
    rerender({ id: "trk_example_2", opts: {} });
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(signals.get("trk_slow")?.aborted).toBe(true);
    expect(result.current.detail?.track_id).toBe("trk_example_2");
  });

  it("surfaces a 404 as a typed error and can reload", async () => {
    server.use(
      http.get(`${BASE}/api/tracks/:id`, () => HttpResponse.json(fixtures.error_track_not_found, { status: 404 })),
    );
    const { result } = render("trk_example_9");
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error).toMatchObject({ kind: "http", code: "track_not_found", status: 404 });
    expect(result.current.detail).toBeNull();
    server.resetHandlers();
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.error).toBeNull();
  });

  it("keeps details when only the neighbors fail", async () => {
    server.use(
      http.get(`${BASE}/api/tracks/:id/neighbors`, () => HttpResponse.json(fixtures.error_internal, { status: 500 })),
    );
    const { result } = render("trk_example_1", { withNeighbors: true });
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.detail).not.toBeNull();
    expect(result.current.neighbors).toBeNull();
    expect(result.current.neighborsError?.code).toBe("internal_error");
  });
});
