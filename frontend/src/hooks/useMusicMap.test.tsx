import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import type { MapPointsResponse } from "../api/types";
import { fixtures } from "../mocks/fixtures";
import { generateMapPoints } from "../mocks/generateMapPoints";
import { handlersFor } from "../mocks/handlers";
import { server } from "../mocks/server";
import { useMusicMap, type UseMusicMapOptions } from "./useMusicMap";

const BASE = "http://api.test";
const client = createApiClient({ baseUrl: BASE });
const ALL = [...fixtures.map_points_page1.points, ...fixtures.map_points_page2.points].map((p) => p.track_id);

function render(options: UseMusicMapOptions = {}) {
  return renderHook(() => useMusicMap({ client, ...options }));
}

function recordPointRequests() {
  const urls: URL[] = [];
  server.events.on("request:start", ({ request }) => {
    const url = new URL(request.url);
    if (url.pathname === "/api/map/points") urls.push(url);
  });
  return urls;
}

describe("useMusicMap", () => {
  it("walks every page automatically", async () => {
    const { result } = render({ pageSize: 2 });
    expect(result.current.status).toBe("loading");
    expect(result.current.availability).toBe("loading");
    await waitFor(() => expect(result.current.hasMore).toBe(false));
    await waitFor(() => expect(result.current.points).toHaveLength(ALL.length));
    expect(result.current.points.map((p) => p.track_id)).toEqual(ALL);
    expect(result.current.status).toBe("success");
    expect(result.current.availability).toBe("available");
    expect(result.current.projectionVersion).toBe(fixtures.map_points_page1.projection_version);
    expect(result.current.meta?.n_points).toBe(ALL.length);
  });

  it("loads pages on demand without autoLoad", async () => {
    const { result } = render({ pageSize: 3, autoLoad: false });
    await waitFor(() => expect(result.current.points).toHaveLength(3));
    expect(result.current.hasMore).toBe(true);
    await act(async () => {
      await result.current.loadMore();
    });
    expect(result.current.points.map((p) => p.track_id)).toEqual(ALL);
    expect(result.current.hasMore).toBe(false);
    await act(async () => {
      await result.current.loadMore(); // nothing left: no request, no change
    });
    expect(result.current.points).toHaveLength(ALL.length);
  });

  it("stops at maxPoints", async () => {
    server.use(...handlersFor("happy", { mapPoints: 50 }));
    const { result } = render({ pageSize: 10, maxPoints: 20 });
    await waitFor(() => expect(result.current.points).toHaveLength(20));
    expect(result.current.hasMore).toBe(true);
  });

  it("restarts from the first page when filters change", async () => {
    const urls = recordPointRequests();
    const { result } = render({ pageSize: 2 });
    await waitFor(() => expect(result.current.points).toHaveLength(ALL.length));
    act(() => result.current.setFilters({ genre: "Folk" }));
    expect(result.current.points).toEqual([]); // old points are not shown under new filters
    await waitFor(() => expect(result.current.status).toBe("success"));
    await waitFor(() => expect(result.current.hasMore).toBe(false));
    expect(result.current.points.every((p) => p.genre === "Folk")).toBe(true);
    const folkRequests = urls.filter((u) => u.searchParams.get("genre") === "Folk");
    expect(folkRequests[0]?.searchParams.has("cursor")).toBe(false);
    const count = urls.length;
    act(() => result.current.setFilters({ genre: "Folk" })); // same filters: no refetch
    expect(urls.length).toBe(count);
    act(() => result.current.resetFilters());
    await waitFor(() => expect(result.current.points).toHaveLength(ALL.length));
    server.events.removeAllListeners();
  });

  it("resets when the projection version changes mid-walk", async () => {
    let calls = 0;
    server.use(
      http.get(`${BASE}/api/map/points`, ({ request }) => {
        calls += 1;
        const cursor = new URL(request.url).searchParams.get("cursor");
        // the first walk sees the map rebuilt between page 1 and page 2
        const version = calls >= 2 ? "umap-rebuilt" : "umap-example";
        const page: MapPointsResponse = cursor ? fixtures.map_points_page2 : fixtures.map_points_page1;
        return HttpResponse.json({ ...page, projection_version: version });
      }),
    );
    const { result } = render({ pageSize: 3 });
    await waitFor(() => expect(result.current.projectionVersion).toBe("umap-rebuilt"));
    await waitFor(() => expect(result.current.hasMore).toBe(false));
    expect(result.current.points.map((p) => p.track_id)).toEqual(ALL);
    expect(calls).toBe(4); // page 1 (old), page 2 (new: reset), page 1 + page 2 (new)
  });

  it("exposes the map-down scenario as unavailable", async () => {
    server.use(...handlersFor("map-down"));
    const { result } = render();
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.availability).toBe("unavailable");
    expect(result.current.points).toEqual([]);
    expect(result.current.error?.code).toBe("projection_unavailable");
    expect(result.current.meta?.status).toBe("unavailable");
  });

  it("reports other failures as errors, not as an unavailable map", async () => {
    server.use(...handlersFor("errors"));
    const { result } = render();
    await waitFor(() => expect(result.current.availability).toBe("error"));
    expect(result.current.error?.code).toBe("internal_error");
  });

  it("requests nothing while disabled", async () => {
    const urls = recordPointRequests();
    const { result } = render({ enabled: false });
    expect(result.current.status).toBe("idle");
    await new Promise((r) => setTimeout(r, 20));
    expect(urls).toHaveLength(0);
    server.events.removeAllListeners();
  });

  it("selection callbacks", async () => {
    const { result } = render();
    act(() => {
      result.current.select("trk_a");
      result.current.select("trk_b");
      result.current.select("trk_a");
    });
    expect([...result.current.selectedTrackIds]).toEqual(["trk_a", "trk_b"]);
    act(() => result.current.deselect("trk_a"));
    act(() => result.current.toggle("trk_c"));
    act(() => result.current.toggle("trk_b"));
    expect([...result.current.selectedTrackIds]).toEqual(["trk_c"]);
    act(() => result.current.clearSelection());
    expect(result.current.selectedTrackIds.size).toBe(0);
    await waitFor(() => expect(result.current.status).toBe("success"));
  });

  it("serves large synthetic maps", async () => {
    server.use(...handlersFor("happy", { mapPoints: 10_000 }));
    const { result } = render({ pageSize: 5000 });
    await waitFor(() => expect(result.current.points).toHaveLength(10_000));
    expect(result.current.points[0]).toEqual(generateMapPoints(1)[0]);
  });
});
