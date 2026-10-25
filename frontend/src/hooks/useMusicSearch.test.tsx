import { act, renderHook, waitFor } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import type { SearchRequest, SearchResponse } from "../api/types";
import { fixtures } from "../mocks/fixtures";
import { handlersFor } from "../mocks/handlers";
import { server } from "../mocks/server";
import { useMusicSearch } from "./useMusicSearch";

const BASE = "http://api.test";
const client = createApiClient({ baseUrl: BASE });

function plate(query: string, sessionId = "ses_example_1"): SearchResponse {
  return { ...fixtures.search_ok, session_id: sessionId, query_id: `qry_${query}`, change_summary: [query] };
}

/** Requests the mock received, in order. */
function recordSearches(respond: (body: SearchRequest) => Promise<SearchResponse> | SearchResponse) {
  const bodies: SearchRequest[] = [];
  server.use(
    http.post(`${BASE}/api/search`, async ({ request }) => {
      const body = (await request.json()) as SearchRequest;
      bodies.push(body);
      return HttpResponse.json(await respond(body));
    }),
  );
  return bodies;
}

describe("useMusicSearch", () => {
  it("goes idle → loading → success and exposes the plate and ids", async () => {
    const { result } = renderHook(() => useMusicSearch({ client }));
    expect(result.current.status).toBe("idle");
    let pending!: Promise<SearchResponse | null>;
    act(() => {
      pending = result.current.search("chill flute");
    });
    expect(result.current.status).toBe("loading");
    expect(result.current.isRefreshing).toBe(false);
    await act(async () => {
      await pending;
    });
    expect(result.current.status).toBe("success");
    expect(result.current.data?.outcome).toBe("ok");
    expect(result.current.sessionId).toBe("ses_example_1");
    expect(result.current.queryId).toMatch(/^qry_/);
    expect(result.current.lastQuery).toBe("chill flute");
  });

  it("never lets an out-of-order response overwrite a newer one", async () => {
    // a fetch that ignores aborts, so only the sequence guard protects the state
    const stubborn = createApiClient({
      baseUrl: BASE,
      fetch: (input, init) => {
        const rest: RequestInit = { ...init };
        delete rest.signal;
        return fetch(input, rest);
      },
    });
    recordSearches(async (body) => {
      await delay(body.query === "slow" ? 80 : 5);
      return plate(body.query);
    });
    const { result } = renderHook(() => useMusicSearch({ client: stubborn }));
    let slow!: Promise<SearchResponse | null>;
    let fast!: Promise<SearchResponse | null>;
    act(() => {
      slow = result.current.search("slow");
    });
    act(() => {
      fast = result.current.search("fast");
    });
    await act(async () => {
      expect(await fast).not.toBeNull();
      expect(await slow).toBeNull(); // arrived later, dropped
    });
    expect(result.current.queryId).toBe("qry_fast");
    expect(result.current.data?.change_summary).toEqual(["fast"]);
  });

  it("cancels the previous request when a new search starts", async () => {
    const signals: AbortSignal[] = [];
    server.use(
      http.post(`${BASE}/api/search`, async ({ request }) => {
        signals.push(request.signal);
        await delay(30);
        return HttpResponse.json(plate("x"));
      }),
    );
    const { result } = renderHook(() => useMusicSearch({ client }));
    await act(async () => {
      void result.current.search("first");
      await result.current.search("second");
    });
    expect(signals[0]?.aborted).toBe(true);
    expect(result.current.status).toBe("success");
    expect(result.current.error).toBeNull();
  });

  it("aborts the in-flight request on unmount", async () => {
    let seen: AbortSignal | null = null;
    server.use(
      http.post(`${BASE}/api/search`, async ({ request }) => {
        seen = request.signal;
        await delay("infinite");
        return HttpResponse.json(plate("never"));
      }),
    );
    const { result, unmount } = renderHook(() => useMusicSearch({ client }));
    act(() => {
      void result.current.search("hang");
    });
    await waitFor(() => expect(seen).not.toBeNull());
    unmount();
    expect(seen!.aborted).toBe(true);
  });

  it("keeps the session id across searches until reset or newSession", async () => {
    const bodies = recordSearches((body) => plate(body.query, body.session_id ?? "ses_new"));
    const { result } = renderHook(() => useMusicSearch({ client, limit: 7 }));
    await act(async () => {
      await result.current.search("first");
      await result.current.search("more electronic");
      await result.current.search("fresh", { newSession: true, limit: 3 });
    });
    expect(bodies.map((b) => [b.session_id, b.limit])).toEqual([
      [null, 7],
      ["ses_new", 7],
      [null, 3],
    ]);
    act(() => result.current.reset());
    expect(result.current.status).toBe("idle");
    expect(result.current.data).toBeNull();
    expect(result.current.sessionId).toBeNull();
  });

  it("keeps the previous plate while refreshing", async () => {
    recordSearches(async (body) => {
      await delay(20);
      return plate(body.query);
    });
    const { result } = renderHook(() => useMusicSearch({ client }));
    await act(async () => {
      await result.current.search("first");
    });
    let pending!: Promise<SearchResponse | null>;
    act(() => {
      pending = result.current.search("second");
    });
    expect(result.current.isRefreshing).toBe(true);
    expect(result.current.queryId).toBe("qry_first");
    await act(async () => {
      await pending;
    });
    expect(result.current.isRefreshing).toBe(false);
    expect(result.current.queryId).toBe("qry_second");
  });

  it("refreshes after feedback: applyRefreshed and refresh()", async () => {
    const bodies = recordSearches((body) => plate(`${body.query}-again`, body.session_id ?? "ses_1"));
    const { result } = renderHook(() => useMusicSearch({ client }));
    await act(async () => {
      await result.current.search("chill flute");
    });
    const refreshed = { ...plate("refined", "ses_1"), change_summary: ["excluded trk_example_1"] };
    act(() => result.current.applyRefreshed(refreshed));
    expect(result.current.data).toBe(refreshed);
    expect(result.current.queryId).toBe("qry_refined");
    await act(async () => {
      await result.current.refresh();
    });
    expect(bodies.at(-1)).toEqual({ query: "chill flute", session_id: "ses_1" });
  });

  it("surfaces API errors and keeps the last good plate", async () => {
    const { result } = renderHook(() => useMusicSearch({ client }));
    await act(async () => {
      await result.current.search("chill flute");
    });
    server.use(...handlersFor("errors"));
    await act(async () => {
      expect(await result.current.search("again")).toBeNull();
    });
    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatchObject({ kind: "http", code: "internal_error", status: 500 });
    expect(result.current.data?.outcome).toBe("ok");
  });

  it("exposes degraded and non-ok outcomes as data, not errors", async () => {
    const { result } = renderHook(() => useMusicSearch({ client }));
    server.use(...handlersFor("degraded-semantic"));
    await act(async () => {
      await result.current.search("x");
    });
    expect(result.current.status).toBe("success");
    expect(result.current.data?.warnings.map((w) => w.code)).toEqual(["semantic_unavailable"]);
    server.use(...handlersFor("needs-clarification"));
    await act(async () => {
      await result.current.search("no vocals with female vocals");
    });
    expect(result.current.data?.outcome).toBe("needs_clarification");
  });
});
