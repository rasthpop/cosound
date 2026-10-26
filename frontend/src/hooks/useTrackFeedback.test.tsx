import { act, renderHook } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import type { FeedbackRequest, FeedbackResponse } from "../api/types";
import { fixtures } from "../mocks/fixtures";
import { handlersFor } from "../mocks/handlers";
import { server } from "../mocks/server";
import { PLATE_KEY, useTrackFeedback } from "./useTrackFeedback";
import { useMusicSearch } from "./useMusicSearch";

const BASE = "http://api.test";
const client = createApiClient({ baseUrl: BASE });

function useBoth() {
  const search = useMusicSearch({ client });
  const feedback = useTrackFeedback(search, { client });
  return { search, feedback };
}

async function searched() {
  const hook = renderHook(useBoth);
  await act(async () => {
    await hook.result.current.search.search("chill flute");
  });
  return hook;
}

describe("useTrackFeedback", () => {
  it("accepted feedback with refresh pushes the refreshed plate into the search", async () => {
    const { result } = await searched();
    const before = result.current.search.queryId;
    let response: FeedbackResponse | null = null;
    await act(async () => {
      response = await result.current.feedback.submit(
        { trackId: "trk_example_1", eventType: "NOT_RELEVANT" },
        { refresh: true },
      );
    });
    expect(response!.accepted).toBe(true);
    expect(result.current.feedback.byTrack.trk_example_1?.status).toBe("success");
    expect(result.current.feedback.lastResponse).toBe(response);
    expect(result.current.search.queryId).not.toBe(before);
    expect(result.current.search.data).toBe(response!.refreshed);
  });

  it("sends the current session and query ids and only the given fields", async () => {
    const bodies: FeedbackRequest[] = [];
    server.use(
      http.post(`${BASE}/api/feedback`, async ({ request }) => {
        bodies.push((await request.json()) as FeedbackRequest);
        return HttpResponse.json(fixtures.feedback_rejected);
      }),
    );
    const { result } = await searched();
    await act(async () => {
      await result.current.feedback.submit({ trackId: "trk_example_2", eventType: "MORE_OF_ATTRIBUTE", attribute: "electronic", value: true });
    });
    expect(bodies[0]).toEqual({
      session_id: result.current.search.sessionId,
      query_id: result.current.search.queryId,
      track_id: "trk_example_2",
      event_type: "MORE_OF_ATTRIBUTE",
      attribute: "electronic",
      value: true,
    });
  });

  it("rejected feedback is a response, not an error, and leaves the plate alone", async () => {
    const { result } = await searched();
    const plate = result.current.search.data;
    await act(async () => {
      await result.current.feedback.submit({ freeText: "the weather is lovely" }, { refresh: true });
    });
    const state = result.current.feedback.byTrack[PLATE_KEY];
    expect(state?.status).toBe("success");
    expect(state?.response?.accepted).toBe(false);
    expect(state?.response?.reason).toBeTruthy();
    expect(result.current.search.data).toBe(plate);
  });

  it("tracks pending state per track", async () => {
    server.use(
      http.post(`${BASE}/api/feedback`, async ({ request }) => {
        const body = (await request.json()) as FeedbackRequest;
        await delay(body.track_id === "trk_slow" ? 60 : 5);
        return HttpResponse.json(fixtures.feedback_rejected);
      }),
    );
    const { result } = await searched();
    let slow!: Promise<unknown>;
    let fast!: Promise<unknown>;
    act(() => {
      slow = result.current.feedback.submit({ trackId: "trk_slow", eventType: "SELECT_TRACK" });
      fast = result.current.feedback.submit({ trackId: "trk_fast", eventType: "SELECT_TRACK" });
    });
    expect(result.current.feedback.isPending("trk_slow")).toBe(true);
    expect(result.current.feedback.isPending("trk_fast")).toBe(true);
    expect(result.current.feedback.isPending("trk_other")).toBe(false);
    await act(async () => {
      await fast;
    });
    expect(result.current.feedback.isPending("trk_fast")).toBe(false);
    expect(result.current.feedback.isPending("trk_slow")).toBe(true);
    await act(async () => {
      await slow;
    });
    expect(result.current.feedback.isPending("trk_slow")).toBe(false);
  });

  it("an invalid event surfaces a typed ApiError", async () => {
    const { result } = await searched();
    server.use(...handlersFor("errors"));
    await act(async () => {
      expect(await result.current.feedback.submit({ trackId: "trk_example_9", eventType: "NOT_RELEVANT" })).toBeNull();
    });
    expect(result.current.feedback.byTrack.trk_example_9?.error).toMatchObject({
      kind: "http",
      code: "track_not_in_results",
      status: 409,
    });
  });

  it("refuses to send feedback before there is a search", async () => {
    const { result } = renderHook(useBoth);
    await act(async () => {
      await result.current.feedback.submit({ trackId: "trk_example_1", eventType: "NOT_RELEVANT" });
    });
    expect(result.current.feedback.byTrack.trk_example_1?.error?.code).toBe("no_active_search");
  });
});
