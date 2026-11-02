// The Discover screen (ui.md §3, §5): the one page of the app. A container — it calls the hooks,
// turns their state into view props and view events into hook actions, and owns only UI state
// (the typed text, which track is selected, hovered or playing, camera requests). Results are
// shown in API order. Selecting a row and selecting a point are the same action (`selectTrack`).
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type { ApiError, Capabilities, SearchResponse } from "@/api/types";
import { boundsOf } from "@/components/map/fitBounds";
import type { FitRequest } from "@/components/map/TrackMap";
import { ChangeStrip } from "@/components/feedback/ChangeStrip";
import { FeedbackActions } from "@/components/feedback/FeedbackActions";
import type { TrackFeedback as TrackFeedbackEvent, TrackFeedbackType } from "@/components/feedback/types";
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
import { PLATE_KEY, useMediaUrl, useMusicMap, useMusicSearch, useSystemStatus, useTrackFeedback, type FeedbackInput, type MusicMap } from "@/hooks";

import { isDetailsPlayer, useSinglePlayback } from "./audio";
import { ANNOUNCE_SEARCHING, announceRefined, announceSearch, EXAMPLE_QUERIES } from "./copy";
import { feedbackMessage, feedbackStatus, queryInstruments, stripFor } from "./feedback";
import { DetailsLayer } from "./DetailsLayer";
import { DiscoverLayout, useIsDesktop } from "./layout";
import { MAP_LABEL, useMapLayer } from "./MapLayer";
import { locate, pointBounds, resultsOnMap } from "./selection";
import { useShortcuts } from "./useShortcuts";

const NONE: ReadonlySet<string> = new Set();
const NO_RESULTS: SearchResponse["results"] = [];
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
  hovered: boolean;
  playing: boolean;
  onTrackSelect: (id: string) => void;
  onTrackHover: (id: string | null) => void;
  onPlay: (id: string | null) => void;
  actions: ReactNode;
}) {
  const playUrl = useMediaUrl(props.result.preview_url);
  return (
    <ResultRow
      result={props.result}
      playUrl={playUrl}
      playing={props.playing}
      selected={props.selected}
      hovered={props.hovered}
      actions={props.actions}
      onTrackSelect={props.onTrackSelect}
      onTrackHover={props.onTrackHover}
      onPlay={props.onPlay}
    />
  );
}

export function DiscoverPage() {
  const search = useMusicSearch();
  const system = useSystemStatus();
  const map = useMusicMap();
  const feedback = useTrackFeedback(search);
  // SELECT_TRACK has its own instance so a selection never shows up as a row's feedback status
  const selectionFeedback = useTrackFeedback(search);
  const desktop = useIsDesktop();

  const [text, setText] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  // which gesture each track's feedback status belongs to, and whose result the strip shows
  const [lastEvent, setLastEvent] = useState<Record<string, TrackFeedbackType>>({});
  const [stripKey, setStripKey] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  // camera requests for the map, and whether "reset view" cleared the current plate's highlight
  const [fit, setFit] = useState<FitRequest | null>(null);
  const [highlightCleared, setHighlightCleared] = useState(false);
  const cameraRequests = useRef(0);
  // where focus returns when the drawer closes: the row or the map the selection came from
  const selectionOrigin = useRef<HTMLElement | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const focusInput = () => inputRef.current?.focus();
  useShortcuts({
    "/": (event) => {
      event.preventDefault();
      focusInput();
    },
  });

  // one clip at a time; when the drawer's player starts, no row is playing any more
  useSinglePlayback((audio) => {
    if (isDetailsPlayer(audio)) setPlayingId(null);
  });

  // flow 1 (idle): the input is focused on arrival, so the examples are visible
  useEffect(() => inputRef.current?.focus(), []);

  const runSearch = (query: string) => {
    setSelectedId(null);
    map.clearSelection();
    setStripKey(null);
    void search.search(query);
  };
  // every gesture refreshes the plate from the server (flow 4); nothing is changed locally
  const sendFeedback = (input: FeedbackInput) => {
    setStripKey(input.trackId ?? PLATE_KEY);
    void feedback.submit(input, { refresh: true });
  };
  const onTrackFeedback = (event: TrackFeedbackEvent) => {
    setLastEvent((prev) => ({ ...prev, [event.trackId]: event.eventType }));
    sendFeedback(event);
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
  const results = plate?.outcome === "ok" ? plate.results : NO_RESULTS;
  // memoized: a stable set keeps the map's point layer from rebuilding on every hover
  const onMap = useMemo(() => resultsOnMap(results, map.points, map.projectionVersion), [results, map.points, map.projectionVersion]);

  // a new plate (search or refinement) lights up its results and fits the camera to them, once
  // per plate and projection (adjusting state during render, no effect)
  const plateKey = plate ? `${plate.query_id ?? ""}|${map.projectionVersion ?? ""}` : null;
  const [fittedPlate, setFittedPlate] = useState<string | null>(null);
  if (plateKey !== fittedPlate) {
    setFittedPlate(plateKey);
    setHighlightCleared(false);
    if (onMap.bounds) setFit({ bounds: onMap.bounds, key: `plate:${plateKey}` });
  }
  const highlighted = highlightCleared ? NONE : onMap.ids;

  /** The one selection action, for rows, points, the map list and neighbors. */
  const mapRegion = () => document.querySelector<HTMLElement>(`[role=region][aria-label="${MAP_LABEL}"]`);
  /** `origin`: where focus returns when the drawer closes; by default the focused row or button. */
  const selectTrack = (trackId: string, origin?: HTMLElement | null) => {
    const active = document.activeElement;
    // a neighbor clicked inside the drawer keeps the original origin
    if (origin !== undefined) selectionOrigin.current = origin;
    else if (!(active instanceof HTMLElement && active.closest("[role=dialog]"))) {
      selectionOrigin.current = active instanceof HTMLElement && active !== document.body ? active : mapRegion();
    }
    setSelectedId(trackId);
    map.clearSelection();
    map.select(trackId);
    const at = locate(trackId, map.points, results, map.projectionVersion);
    if (at) setFit({ bounds: pointBounds(at), key: `select:${++cameraRequests.current}` });
    // D4: recorded only within a search session; without one, the map click just opens details
    if (search.sessionId) void selectionFeedback.submit({ trackId, eventType: "SELECT_TRACK" });
  };
  const closeDetails = () => {
    setSelectedId(null);
    map.clearSelection();
  };
  const restoreFocus = (event: Event) => {
    event.preventDefault();
    const origin = selectionOrigin.current;
    if (origin?.isConnected) origin.focus();
    else inputRef.current?.focus();
  };
  const resetView = () => {
    setHighlightCleared(true);
    const all = map.meta?.bounds ?? boundsOf(map.points);
    if (all) setFit({ bounds: all, key: `reset:${++cameraRequests.current}` });
  };
  const mapLayer = useMapLayer({
    map,
    highlightedTrackIds: highlighted,
    dimUnhighlighted: highlighted.size > 0,
    hoveredTrackId: hoveredId,
    fitTo: fit,
    onTrackSelect: (id) => selectTrack(id),
    onPointSelect: (id) => selectTrack(id, mapRegion()),
    onTrackHover: setHoveredId,
    onReset: resetView,
    resultsShown: desktop && plate !== null,
  });

  const query = plate?.interpreted_query.original_query ?? search.lastQuery;
  const offline = isOffline(search.error) || isOffline(system.error);
  const capabilities = currentCapabilities(plate, system.capabilities, map.availability);
  const instruments = queryInstruments(plate?.interpreted_query);

  // "what changed": the latest refinement. A row's failure is already shown on the row, so the
  // strip only reports the row's applied changes; chip and free-text feedback report everything.
  let strip = stripKey ? stripFor(feedback.byTrack[stripKey]) : null;
  if (strip && stripKey !== PLATE_KEY && strip.status !== "applied") strip = null;
  const changeStrip =
    strip && plate ? (
      <ChangeStrip
        changeSummary={strip.response?.change_summary ?? []}
        changes={strip.response?.changes ?? []}
        status={strip.status}
        message={strip.message}
        originalQuery={plate.interpreted_query.original_query}
        onDismiss={() => setStripKey(null)}
      />
    ) : null;

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
              hovered={result.track_id === hoveredId}
              playing={result.track_id === playingId}
              onTrackSelect={selectTrack}
              onTrackHover={setHoveredId}
              onPlay={setPlayingId}
              actions={
                <FeedbackActions
                  trackId={result.track_id}
                  title={result.title}
                  status={feedbackStatus(feedback.byTrack[result.track_id])}
                  lastEvent={lastEvent[result.track_id] ?? null}
                  message={feedbackMessage(feedback.byTrack[result.track_id])}
                  instruments={instruments}
                  onFeedback={onTrackFeedback}
                />
              }
            />
          ))}
        </ResultsList>
      );
  }
  const selectedResult = selectedId ? (results.find((r) => r.track_id === selectedId) ?? null) : null;
  const details = (
    <DetailsLayer
      trackId={selectedId}
      projectionVersion={map.projectionVersion}
      result={selectedResult}
      actions={
        selectedResult && (
          <FeedbackActions
            trackId={selectedResult.track_id}
            title={selectedResult.title}
            status={feedbackStatus(feedback.byTrack[selectedResult.track_id])}
            lastEvent={lastEvent[selectedResult.track_id] ?? null}
            message={feedbackMessage(feedback.byTrack[selectedResult.track_id])}
            instruments={instruments}
            layout="labels"
            onFeedback={onTrackFeedback}
          />
        )
      }
      variant={desktop ? "desktop" : "mobile"}
      onClose={closeDetails}
      onCloseAutoFocus={restoreFocus}
      onTrackSelect={selectTrack}
    />
  );

  // a clarification question replaces the plate; it is answered under the bar
  const clarifying = search.status !== "error" && plate?.outcome === "needs_clarification";

  const panel =
    body !== null ? (
      <ResultsPanel query={query} count={count} stale={search.isRefreshing} changeStrip={changeStrip} variant={desktop ? "panel" : "sheet"}>
        {body}
      </ResultsPanel>
    ) : null;

  let announcement = "";
  if (search.status === "loading") announcement = ANNOUNCE_SEARCHING;
  else if (search.status === "success" && plate) {
    announcement = strip?.status === "applied" ? announceRefined(plate, query ?? "") : announceSearch(plate, query ?? "");
  }

  return (
    <DiscoverLayout
      map={mapLayer.canvas}
      controls={mapLayer.controls}
      search={
        <>
          <SearchBar
            value={text}
            onValueChange={setText}
            onQuerySubmit={runSearch}
            // D2: with results on screen, the Refine toggle sends the text as free-text feedback
            canRefine={plate !== null && plate.query_id !== null}
            onRefineSubmit={(freeText) => sendFeedback({ freeText })}
            loading={search.status === "loading" || feedback.isPending(PLATE_KEY)}
            stale={search.isRefreshing}
            examples={EXAMPLE_QUERIES}
            inputRef={inputRef}
          />
          {plate && search.status !== "error" && (
            <QueryChips
              query={plate.interpreted_query}
              interpreterFallback={plate.capabilities.llm_interpreter === "fallback"}
              // D1: soft chips send More/Less of that attribute; hard constraints send nothing
              onAttributeFeedback={({ eventType, attribute, value }) => sendFeedback({ eventType, attribute, value })}
              onEditQuery={editQuery}
            />
          )}
          {clarifying && plate.clarification_question && (
            // the reply is a follow-up search in the same session
            <ClarificationPrompt key={plate.query_id} question={plate.clarification_question} onReply={runSearch} />
          )}
        </>
      }
      results={desktop ? panel : null}
      overlays={
        <>
          {desktop ? null : panel}
          {details}
        </>
      }
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
      detailsOpen={selectedId !== null}
    />
  );
}
