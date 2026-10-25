// Map data for any renderer: projection metadata, paginated points, filters and selection.
//
// - Points come from the API exactly as sent: no coordinate maths, no similarity, no deck.gl.
// - `autoLoad` (default) walks every page; otherwise call `loadMore()`.
// - Changing filters restarts from the first page. A page from a different projection
//   version than the loaded ones resets everything (points from two maps never mix).
// - `availability` is "unavailable" when the backend has no usable projection; search is
//   unaffected and the UI can say so.
import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient, isAbortError, isApiError, type ApiClient } from "../api/client";
import type { ApiError, MapFilters, MapMeta, MapPoint, MapPointsResponse } from "../api/types";
import { toApiError, type RequestStatus } from "./status";

export type MapAvailability = "loading" | "available" | "unavailable" | "error";

export interface UseMusicMapOptions {
  client?: ApiClient;
  /** Points per request (API maximum 5000). */
  pageSize?: number;
  /** Load every page automatically (default) or wait for `loadMore()`. */
  autoLoad?: boolean;
  /** Stop auto-loading after this many points. */
  maxPoints?: number;
  /** Nothing is requested while false. */
  enabled?: boolean;
  initialFilters?: MapFilters;
}

export interface MusicMap {
  availability: MapAvailability;
  meta: MapMeta | null;
  /** Status of the point list (first page). */
  status: RequestStatus;
  points: readonly MapPoint[];
  projectionVersion: string | null;
  hasMore: boolean;
  isLoadingMore: boolean;
  error: ApiError | null;
  loadMore: () => Promise<void>;
  filters: MapFilters;
  setFilters: (filters: MapFilters) => void;
  resetFilters: () => void;
  /** Refetch meta and points from the start. */
  reload: () => void;
  selectedTrackIds: ReadonlySet<string>;
  select: (trackId: string) => void;
  deselect: (trackId: string) => void;
  toggle: (trackId: string) => void;
  clearSelection: () => void;
}

const UNAVAILABLE_CODES = new Set(["projection_unavailable", "projection_mismatch"]);
const DEFAULT_PAGE_SIZE = 500;

interface PointsState {
  key: string;
  points: MapPoint[];
  nextCursor: string | null;
  version: string | null;
  error: ApiError | null;
}

interface MetaState {
  generation: number;
  meta: MapMeta | null;
  error: ApiError | null;
}

const asApiError = (cause: unknown): ApiError => (isApiError(cause) ? cause.toJSON() : toApiError(cause));

function clean(filters: MapFilters): MapFilters {
  const out: MapFilters = {};
  if (filters.genre) out.genre = filters.genre;
  if (filters.style) out.style = filters.style;
  if (filters.artist_id) out.artist_id = filters.artist_id;
  if (filters.has_audio !== undefined && filters.has_audio !== null) out.has_audio = filters.has_audio;
  return out;
}

export function useMusicMap(options: UseMusicMapOptions = {}): MusicMap {
  const client = options.client ?? apiClient;
  const pageSize = options.pageSize ?? DEFAULT_PAGE_SIZE;
  const autoLoad = options.autoLoad ?? true;
  const maxPoints = options.maxPoints ?? Number.POSITIVE_INFINITY;
  const enabled = options.enabled ?? true;

  const [initialFilters] = useState(() => clean(options.initialFilters ?? {}));
  const [filters, setFilterState] = useState<MapFilters>(initialFilters);
  const [generation, setGeneration] = useState(0);
  const [metaState, setMetaState] = useState<MetaState | null>(null);
  const [pointsState, setPointsState] = useState<PointsState | null>(null);
  const [loadingMoreKey, setLoadingMoreKey] = useState<string | null>(null);
  const [selected, setSelected] = useState<ReadonlySet<string>>(() => new Set());
  const moreController = useRef<AbortController | null>(null);

  const requestKey = `${generation}:${JSON.stringify(filters)}`;

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    client
      .getMapMeta({ signal: controller.signal })
      .then((meta) => setMetaState({ generation, meta, error: null }))
      .catch((cause: unknown) => {
        if (!isAbortError(cause)) setMetaState({ generation, meta: null, error: asApiError(cause) });
      });
    return () => controller.abort();
  }, [client, enabled, generation]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    void (async () => {
      let cursor: string | null = null;
      let points: MapPoint[] = [];
      let version: string | null = null;
      try {
        do {
          const query = { ...filters, limit: pageSize, ...(cursor ? { cursor } : {}) };
          const page: MapPointsResponse = await client.getMapPoints(query, { signal: controller.signal });
          if (version !== null && page.projection_version !== version) {
            setGeneration((g) => g + 1); // the map was rebuilt mid-walk: start over
            return;
          }
          version = page.projection_version;
          points = [...points, ...page.points];
          cursor = page.next_cursor;
          setPointsState({ key: requestKey, points, nextCursor: cursor, version, error: null });
        } while (autoLoad && cursor !== null && points.length < maxPoints);
      } catch (cause) {
        if (isAbortError(cause)) return;
        setPointsState({ key: requestKey, points, nextCursor: cursor, version, error: asApiError(cause) });
      }
    })();
    return () => controller.abort();
  }, [autoLoad, client, enabled, filters, maxPoints, pageSize, requestKey]);

  useEffect(() => () => moreController.current?.abort(), []);

  const current = pointsState !== null && pointsState.key === requestKey ? pointsState : null;

  const loadMore = useCallback(async () => {
    if (current === null || current.nextCursor === null || loadingMoreKey === requestKey) return;
    const controller = new AbortController();
    moreController.current = controller;
    setLoadingMoreKey(requestKey);
    try {
      const page = await client.getMapPoints(
        { ...filters, limit: pageSize, cursor: current.nextCursor },
        { signal: controller.signal },
      );
      if (page.projection_version !== current.version) {
        setGeneration((g) => g + 1);
        return;
      }
      setPointsState((state) =>
        state === null || state.key !== requestKey
          ? state
          : { ...state, points: [...state.points, ...page.points], nextCursor: page.next_cursor },
      );
    } catch (cause) {
      if (!isAbortError(cause)) {
        setPointsState((state) => (state === null || state.key !== requestKey ? state : { ...state, error: asApiError(cause) }));
      }
    } finally {
      setLoadingMoreKey((key) => (key === requestKey ? null : key));
    }
  }, [client, current, filters, loadingMoreKey, pageSize, requestKey]);

  const setFilters = useCallback((next: MapFilters) => {
    const cleaned = clean(next);
    // equal filters keep the same object, so nothing is refetched
    setFilterState((prev) => (JSON.stringify(prev) === JSON.stringify(cleaned) ? prev : cleaned));
  }, []);
  const resetFilters = useCallback(() => setFilterState(initialFilters), [initialFilters]);
  const reload = useCallback(() => setGeneration((g) => g + 1), []);

  const select = useCallback((id: string) => setSelected((s) => (s.has(id) ? s : new Set(s).add(id))), []);
  const deselect = useCallback(
    (id: string) =>
      setSelected((s) => {
        if (!s.has(id)) return s;
        const next = new Set(s);
        next.delete(id);
        return next;
      }),
    [],
  );
  const toggle = useCallback(
    (id: string) =>
      setSelected((s) => {
        const next = new Set(s);
        if (!next.delete(id)) next.add(id);
        return next;
      }),
    [],
  );
  const clearSelection = useCallback(() => setSelected((s) => (s.size === 0 ? s : new Set())), []);

  const meta = metaState?.generation === generation ? metaState.meta : null;
  const metaError = metaState?.generation === generation ? metaState.error : null;
  const error = current?.error ?? metaError;

  let status: RequestStatus = "idle";
  if (enabled) status = current === null ? "loading" : current.error && current.points.length === 0 ? "error" : "success";

  let availability: MapAvailability = "loading";
  if (meta?.status === "unavailable" || (error && UNAVAILABLE_CODES.has(error.code))) availability = "unavailable";
  else if (error) availability = "error";
  else if (meta?.status === "available") availability = "available";

  return {
    availability,
    meta,
    status,
    points: current?.points ?? [],
    projectionVersion: current?.version ?? meta?.projection_version ?? null,
    hasMore: current?.nextCursor != null,
    isLoadingMore: loadingMoreKey === requestKey,
    error,
    loadMore,
    filters,
    setFilters,
    resetFilters,
    reload,
    selectedTrackIds: selected,
    select,
    deselect,
    toggle,
    clearSelection,
  };
}
