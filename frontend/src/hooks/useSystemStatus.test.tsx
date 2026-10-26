import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import { fixtures } from "../mocks/fixtures";
import { server } from "../mocks/server";
import { useSystemStatus } from "./useSystemStatus";

const BASE = "http://api.test";
const client = createApiClient({ baseUrl: BASE });

describe("useSystemStatus", () => {
  it("reports the capabilities of a healthy backend", async () => {
    const { result } = renderHook(() => useSystemStatus({ client }));
    expect(result.current.status).toBe("loading");
    expect(result.current.capabilities).toBeNull();
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.capabilities).toEqual(fixtures.health.capabilities);
    expect(result.current.reasons).toEqual({ semantic: null, map: null });
    expect(result.current.error).toBeNull();
  });

  it("reports degraded capabilities with their reasons", async () => {
    server.use(http.get(`${BASE}/api/health`, () => HttpResponse.json(fixtures.health_degraded)));
    const { result } = renderHook(() => useSystemStatus({ client }));
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.capabilities?.semantic).toBe("unavailable");
    expect(result.current.capabilities?.map).toBe("unavailable");
    expect(result.current.reasons).toEqual({
      semantic: "clap_checkpoint_missing",
      map: "projection_unavailable",
    });
  });

  it("is offline on a network failure and never guesses a capability", async () => {
    server.use(http.get(`${BASE}/api/health`, () => HttpResponse.error()));
    const { result } = renderHook(() => useSystemStatus({ client }));
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error?.kind).toBe("network");
    expect(result.current.capabilities).toBeNull();
    expect(result.current.reasons).toEqual({ semantic: null, map: null });
  });

  it("reload asks again and recovers", async () => {
    let calls = 0;
    server.use(
      http.get(`${BASE}/api/health`, () => {
        calls += 1;
        return calls === 1 ? HttpResponse.error() : HttpResponse.json(fixtures.health);
      }),
    );
    const { result } = renderHook(() => useSystemStatus({ client }));
    await waitFor(() => expect(result.current.status).toBe("error"));
    act(() => result.current.reload());
    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.capabilities).toEqual(fixtures.health.capabilities);
    expect(calls).toBe(2);
  });

  it("keeps the last answer visible while a reload runs", async () => {
    const { result } = renderHook(() => useSystemStatus({ client }));
    await waitFor(() => expect(result.current.status).toBe("success"));
    act(() => result.current.reload());
    expect(result.current.status).toBe("loading");
    expect(result.current.capabilities).toEqual(fixtures.health.capabilities);
    await waitFor(() => expect(result.current.status).toBe("success"));
  });
});
