// Contract harness (P09.T09): a deliberately plain page that drives the four hooks end to end.
// It is NOT the interface: no styling and no design decisions. It only proves that a visual
// layer can search, show a plate, send feedback and page through the map using hooks alone.
// Served only by the dev server at /__dev/harness and never in a production build.
import { useState } from "react";

import { createApiClient } from "../api/client";
import type { FeedbackType } from "../api/types";
import { useMusicMap, useMusicSearch, useTrackDetails, useTrackFeedback } from "../hooks";

const client = createApiClient();

const TRACK_EVENTS: { type: FeedbackType; attribute?: string }[] = [
  { type: "MORE_LIKE_THIS" },
  { type: "LESS_LIKE_THIS" },
  { type: "NOT_RELEVANT" },
  { type: "WRONG_INSTRUMENT", attribute: "flute" },
  { type: "SELECT_TRACK" },
];
const ATTRIBUTE_EVENTS: { type: FeedbackType; attribute: string }[] = [
  { type: "MORE_OF_ATTRIBUTE", attribute: "electronic" },
  { type: "LESS_OF_ATTRIBUTE", attribute: "acoustic" },
];

export function ContractHarness() {
  const search = useMusicSearch({ client, limit: 8 });
  const feedback = useTrackFeedback(search, { client });
  const map = useMusicMap({ client, pageSize: 3, autoLoad: false });
  const [selected, setSelected] = useState<string | null>(null);
  const details = useTrackDetails(selected, {
    client,
    withNeighbors: true,
    k: 3,
    projectionVersion: map.projectionVersion,
  });
  const [query, setQuery] = useState("Something chill with a flute");
  const [freeText, setFreeText] = useState("");
  const [refresh, setRefresh] = useState(true);
  const [genre, setGenre] = useState("");

  const plate = search.data;
  const last = feedback.lastResponse;

  return (
    <main>
      <h1>Contract harness (dev only)</h1>

      <section aria-label="search">
        <h2>Search</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void search.search(query);
          }}
        >
          <input aria-label="query" value={query} onChange={(e) => setQuery(e.target.value)} />
          <button type="submit">search</button>
          <button type="button" onClick={() => void search.refresh()}>
            refresh
          </button>
          <button type="button" onClick={search.reset}>
            reset
          </button>
        </form>
        <dl>
          <dt>status</dt>
          <dd data-testid="search-status">{search.status}</dd>
          <dt>refreshing</dt>
          <dd>{String(search.isRefreshing)}</dd>
          <dt>session</dt>
          <dd data-testid="session-id">{search.sessionId ?? "null"}</dd>
          <dt>query</dt>
          <dd data-testid="query-id">{search.queryId ?? "null"}</dd>
          <dt>error</dt>
          <dd data-testid="search-error">{search.error ? `${search.error.code}: ${search.error.message}` : "null"}</dd>
        </dl>
        {plate && (
          <>
            <dl>
              <dt>outcome</dt>
              <dd data-testid="outcome">{plate.outcome}</dd>
              <dt>clarification</dt>
              <dd>{plate.clarification_question ?? "null"}</dd>
              <dt>no match reasons</dt>
              <dd>{plate.no_match_reasons.join(" | ") || "none"}</dd>
              <dt>capabilities</dt>
              <dd data-testid="capabilities">{JSON.stringify(plate.capabilities)}</dd>
              <dt>warnings</dt>
              <dd data-testid="warnings">{plate.warnings.map((w) => w.code).join(",") || "none"}</dd>
              <dt>change summary</dt>
              <dd data-testid="change-summary">{plate.change_summary.join(" | ") || "none"}</dd>
            </dl>
            <ol data-testid="plate">
              {plate.results.map((r) => (
                <li key={r.track_id} data-testid="plate-item" data-track-id={r.track_id}>
                  <pre>{JSON.stringify({ ...r, description: undefined }, null, 1)}</pre>
                  <p>description: {r.description ?? "null"}</p>
                  {TRACK_EVENTS.map((e) => (
                    <button
                      key={e.type}
                      type="button"
                      disabled={feedback.isPending(r.track_id)}
                      onClick={() => {
                        if (e.type === "SELECT_TRACK") setSelected(r.track_id);
                        void feedback.submit(
                          { trackId: r.track_id, eventType: e.type, attribute: e.attribute ?? null },
                          { refresh },
                        );
                      }}
                    >
                      {e.type}
                    </button>
                  ))}
                  <span>feedback: {feedback.byTrack[r.track_id]?.status ?? "none"}</span>
                </li>
              ))}
            </ol>
          </>
        )}
      </section>

      <section aria-label="feedback">
        <h2>Feedback</h2>
        <label>
          <input type="checkbox" checked={refresh} onChange={(e) => setRefresh(e.target.checked)} /> refresh
        </label>
        {ATTRIBUTE_EVENTS.map((e) => (
          <button
            key={e.type}
            type="button"
            onClick={() => void feedback.submit({ eventType: e.type, attribute: e.attribute }, { refresh })}
          >
            {e.type} {e.attribute}
          </button>
        ))}
        <input aria-label="free text" value={freeText} onChange={(e) => setFreeText(e.target.value)} />
        <button type="button" onClick={() => void feedback.submit({ freeText }, { refresh })}>
          send text
        </button>
        <dl>
          <dt>accepted</dt>
          <dd data-testid="feedback-accepted">{last ? String(last.accepted) : "none"}</dd>
          <dt>reason</dt>
          <dd>{last?.reason ?? "null"}</dd>
          <dt>next action</dt>
          <dd data-testid="next-action">{last?.next_action ?? "none"}</dd>
          <dt>change summary</dt>
          <dd>{last?.change_summary.join(" | ") ?? "none"}</dd>
        </dl>
      </section>

      <section aria-label="details">
        <h2>Track details</h2>
        <p data-testid="details-status">
          {selected ?? "none"}: {details.status}
          {details.error ? ` (${details.error.code})` : ""}
        </p>
        {details.detail && <pre data-testid="details">{JSON.stringify(details.detail, null, 1)}</pre>}
        {details.neighbors && (
          <p data-testid="neighbors">
            {details.neighbors.metric}: {details.neighbors.neighbors.map((n) => n.track_id).join(", ") || "none"}
          </p>
        )}
      </section>

      <section aria-label="map">
        <h2>Map points</h2>
        <p data-testid="map-availability">{map.availability}</p>
        <p>
          version {map.projectionVersion ?? "null"}; status {map.status};{" "}
          <span data-testid="map-count">{map.points.length}</span> points; more: {String(map.hasMore)}
        </p>
        <input aria-label="genre" value={genre} onChange={(e) => setGenre(e.target.value)} />
        <button type="button" onClick={() => map.setFilters(genre ? { genre } : {})}>
          filter
        </button>
        <button type="button" disabled={!map.hasMore || map.isLoadingMore} onClick={() => void map.loadMore()}>
          load more
        </button>
        <ul data-testid="map-points">
          {map.points.map((p) => (
            <li key={p.track_id}>
              <button type="button" onClick={() => map.toggle(p.track_id)}>
                {map.selectedTrackIds.has(p.track_id) ? "[x]" : "[ ]"}
              </button>{" "}
              {p.track_id} ({p.x}, {p.y}) {p.title} / {p.artist ?? "null"} / {p.genre ?? "null"}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
