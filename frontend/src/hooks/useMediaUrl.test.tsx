import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import { fixtures } from "../mocks/fixtures";
import { useMediaUrl } from "./useMediaUrl";

const client = createApiClient({ baseUrl: "http://api.test/" });

describe("useMediaUrl", () => {
  it("passes null through: no clip, no URL", () => {
    const { result } = renderHook(() => useMediaUrl(null, { client }));
    expect(result.current).toBeNull();
  });

  it("resolves an API path against the client's base URL", () => {
    const path = fixtures.search_ok.results[0]!.preview_url;
    const { result } = renderHook(() => useMediaUrl(path, { client }));
    expect(result.current).toBe("http://api.test/api/tracks/trk_example_1/audio");
  });

  it("uses the page origin when the client has no base URL", () => {
    const local = createApiClient({ baseUrl: "" });
    const { result } = renderHook(() => useMediaUrl("/api/tracks/trk_example_1/audio", { client: local }));
    expect(result.current).toBe(`${globalThis.location.origin}/api/tracks/trk_example_1/audio`);
  });

  it("returns a URL the mock audio endpoint serves", async () => {
    const { result } = renderHook(() => useMediaUrl("/api/tracks/trk_example_1/audio", { client }));
    const response = await fetch(result.current!);
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("audio/mpeg");
  });

  it("is stable across renders for the same path", () => {
    const { result, rerender } = renderHook(({ p }) => useMediaUrl(p, { client }), {
      initialProps: { p: "/api/tracks/trk_example_1/audio" as string | null },
    });
    const first = result.current;
    rerender({ p: "/api/tracks/trk_example_1/audio" });
    expect(result.current).toBe(first);
  });
});
