// The Discover screen (ui.md §3, §5): the one page of the app. A container — it calls the hooks,
// turns their state into view props and view events into hook actions, and owns only UI state
// (the typed text, which track is selected or playing). Results are shown in API order.
import { useEffect, useRef, useState, type ReactNode } from "react";

import type { ApiError, Capabilities, SearchResponse } from "@/api/types";
import { ResultRow, type ResultRowData } from "@/components/results/ResultRow";
import { ResultsList, ResultsLoading, ResultsPanel } from "@/components/results/ResultsPanel";
import { ClarificationPrompt } from "@/components/search/ClarificationPrompt";
import { QueryChips } from "@/components/search/QueryChips";
import { SearchBar } from "@/components/search/SearchBar";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { NoConfidentMatch } from "@/components/states/NoConfidentMatch";
import { OfflineState } from "@/components/states/OfflineState";
import { StatusPill } from "@/components/states/StatusPill";
import { useMediaUrl, useMusicMap, useMusicSearch, useSystemStatus, type MusicMap } from "@/hooks";

import { ANNOUNCE_SEARCHING, announceSearch, EXAMPLE_QUERIES } from "./copy";
import { DiscoverLayout, useIsDesktop } from "./layout";
import { useShortcuts } from "./useShortcuts";

const isOffline = (error: ApiError | null) => error?.kind === "network";

/** The plate's capabilities when there is one (fresher), else the health check's; the map's own
 * availability wins for `map`, since the map is loaded separately. */
function currentCapabilities(
  plate: SearchResponse | null,
  health: Capabilities | null,
  map: MusicMap["availability"],
): Pick<Capabilities, "semantic" | "map"> | null {
  const base = plate?.capabilities ?? health;
  if (map === "unavailable") return { semantic: base?.semantic ?? "available", map: "unavailable" };
  return base;
}

/** One ranked row with its own playable URL (a hook per row, so it lives in a container). */
function ResultItem(props: {
  result: ResultRowData & { preview_url: string | null };
  selected: boolean;
  playing: boolean;
  onTrackSelect: (id: string) => void;
  onPlay: (id: string | null) => void;
}) {
  const playUrl = useMediaUrl(props.result.preview_url);
  return (
    <ResultRow
      result={props.result}
      playUrl={playUrl}
      playing={props.playing}
      selected={props.selected}
      onTrackSelect={props.onTrackSelect}
      onPlay={props.onPlay}
    />
  );
}

export function DiscoverPage() {
  const search = useMusicSearch();
  const system = useSystemStatus();
  const map = useMusicMap();
  const desktop = useIsDesktop();

  const [text, setText] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const focusInput = () => inputRef.current?.focus();
  useShortcuts({
    "/": (event) => {
      event.preventDefault();
      focusInput();
    },
  });

  // flow 1 (idle): the input is focused on arrival, so the examples are visible
  useEffect(() => inputRef.current?.focus(), []);

  const runSearch = (query: string) => {
    setSelectedId(null);
    void search.search(query);
  };
  const retrySearch = () => {
    if (search.lastQuery) void search.search(search.lastQuery);
  };
  const editQuery = () => {
    const original = search.data?.interpreted_query.original_query ?? search.lastQuery;
    if (original) setText(original);
    focusInput();
  };

  const plate = search.data;
  const query = plate?.interpreted_query.original_query ?? search.lastQuery;
  const offline = isOffline(search.error) || isOffline(system.error);
  const capabilities = currentCapabilities(plate, system.capabilities, map.availability);

  // ── the results panel body, by state ──
  let body: ReactNode = null;
  let count: number | null = null;
  if (search.status === "error") {
    body = isOffline(search.error) ? <OfflineState query={search.lastQuery} onRetry={retrySearch} /> : <ErrorState error={search.error} onRetry={retrySearch} />;
  } else if (plate === null) {
    if (search.status === "loading") body = <ResultsLoading />;
  } else if (plate.outcome === "no_confident_match") {
    count = 0;
    body = <NoConfidentMatch reasons={plate.no_match_reasons} onEditQuery={editQuery} />;
  } else if (plate.outcome === "ok") {
    count = plate.results.length;
    body =
      count === 0 ? (
        <EmptyState query={query} onEditQuery={editQuery} />
      ) : (
        <ResultsList>
          {plate.results.map((result) => (
            <ResultItem
              key={result.track_id}
              result={result}
              selected={result.track_id === selectedId}
              playing={result.track_id === playingId}
              onTrackSelect={setSelectedId}
              onPlay={setPlayingId}
            />
          ))}
        </ResultsList>
      );
  }
  // a clarification question replaces the plate; it is answered under the bar
  const clarifying = search.status !== "error" && plate?.outcome === "needs_clarification";

  const results =
    body !== null ? (
      <ResultsPanel query={query} count={count} stale={search.isRefreshing} variant={desktop ? "panel" : "sheet"}>
        {body}
      </ResultsPanel>
    ) : null;

  let announcement = "";
  if (search.status === "loading") announcement = ANNOUNCE_SEARCHING;
  else if (search.status === "success" && plate) announcement = announceSearch(plate, query ?? "");

  return (
    <DiscoverLayout
      map={<div aria-hidden="true" className="size-full bg-surface-canvas" />}
      search={
        <>
          <SearchBar
            value={text}
            onValueChange={setText}
            onQuerySubmit={runSearch}
            loading={search.status === "loading"}
            stale={search.isRefreshing}
            examples={EXAMPLE_QUERIES}
            inputRef={inputRef}
          />
          {plate && search.status !== "error" && (
            <QueryChips
              query={plate.interpreted_query}
              interpreterFallback={plate.capabilities.llm_interpreter === "fallback"}
              // chip feedback is wired in U04.T02
              onAttributeFeedback={() => {}}
              onEditQuery={editQuery}
            />
          )}
          {clarifying && plate.clarification_question && (
            // the reply is a follow-up search in the same session
            <ClarificationPrompt key={plate.query_id} question={plate.clarification_question} onReply={runSearch} />
          )}
        </>
      }
      results={desktop ? results : null}
      overlays={desktop ? null : results}
      status={
        <StatusPill
          capabilities={capabilities}
          offline={offline}
          onRetry={() => {
            system.reload();
            map.reload();
            if (isOffline(search.error)) retrySearch();
          }}
        />
      }
      announcement={announcement}
    />
  );
}
