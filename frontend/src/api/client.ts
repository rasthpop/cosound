// Typed HTTP client for the backend contract (base.md §14.1). The only place `fetch` is called.
// Requests, cancellation, (de)serialization and error normalization; no business rules.
import type {
  ApiError,
  ApiErrorKind,
  FeedbackRequest,
  FeedbackResponse,
  HealthResponse,
  MapMeta,
  MapPointsQuery,
  MapPointsResponse,
  NeighborsResponse,
  SearchRequest,
  SearchResponse,
  SessionResponse,
  TrackDetail,
} from "./types";

/** Thrown for every failed call; carries the normalized `ApiError` fields. */
export class ApiClientError extends Error implements ApiError {
  readonly kind: ApiErrorKind;
  readonly code: string;
  readonly status: number | null;
  readonly details: Record<string, unknown>;

  constructor(error: ApiError) {
    super(error.message);
    this.name = "ApiClientError";
    this.kind = error.kind;
    this.code = error.code;
    this.status = error.status;
    this.details = error.details;
  }

  toJSON(): ApiError {
    return { kind: this.kind, code: this.code, message: this.message, status: this.status, details: this.details };
  }
}

export function isApiError(value: unknown): value is ApiClientError {
  return value instanceof ApiClientError;
}

export function isAbortError(value: unknown): boolean {
  return isApiError(value) && value.kind === "aborted";
}

export interface RequestOptions {
  signal?: AbortSignal;
}

export interface ClientOptions {
  /** Backend origin; defaults to VITE_API_BASE_URL, else the page's own origin. */
  baseUrl?: string;
  fetch?: typeof fetch;
}

type Query = Record<string, string | number | boolean | null | undefined>;

export interface ApiClient {
  health(options?: RequestOptions): Promise<HealthResponse>;
  search(request: SearchRequest, options?: RequestOptions): Promise<SearchResponse>;
  getTrack(trackId: string, options?: RequestOptions): Promise<TrackDetail>;
  getNeighbors(trackId: string, options?: RequestOptions & { k?: number }): Promise<NeighborsResponse>;
  submitFeedback(request: FeedbackRequest, options?: RequestOptions): Promise<FeedbackResponse>;
  getSession(sessionId: string, options?: RequestOptions): Promise<SessionResponse>;
  getMapMeta(options?: RequestOptions): Promise<MapMeta>;
  getMapPoints(query?: MapPointsQuery, options?: RequestOptions): Promise<MapPointsResponse>;
  /** Absolute URL for an API path such as a track's `preview_url`. */
  resolveUrl(path: string): string;
}

export function createApiClient(options: ClientOptions = {}): ApiClient {
  const baseUrl = options.baseUrl ?? import.meta.env.VITE_API_BASE_URL ?? "";
  const doFetch = options.fetch ?? ((input, init) => globalThis.fetch(input, init));

  const resolveUrl = (path: string, query?: Query): string => {
    const origin = globalThis.location?.origin ?? "http://localhost";
    const url = new URL(`${baseUrl.replace(/\/$/, "")}${path}`, origin);
    for (const [key, value] of Object.entries(query ?? {})) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
    return url.toString();
  };

  async function request<T>(
    method: "GET" | "POST",
    path: string,
    { body, query, signal }: { body?: unknown; query?: Query; signal?: AbortSignal | undefined },
  ): Promise<T> {
    const init: RequestInit = { method, headers: { Accept: "application/json" } };
    if (signal) init.signal = signal;
    if (body !== undefined) {
      init.headers = { ...init.headers, "Content-Type": "application/json" };
      init.body = JSON.stringify(body);
    }
    let response: Response;
    try {
      response = await doFetch(resolveUrl(path, query), init);
    } catch (cause) {
      throw networkError(cause, signal);
    }
    let text: string;
    try {
      text = await response.text();
    } catch (cause) {
      throw networkError(cause, signal);
    }
    if (!response.ok) {
      throw httpError(response, text);
    }
    try {
      return JSON.parse(text) as T;
    } catch {
      throw new ApiClientError({
        kind: "parse",
        code: "invalid_response",
        message: `The server sent a response that is not valid JSON (${method} ${path}).`,
        status: response.status,
        details: {},
      });
    }
  }

  const enc = encodeURIComponent;
  return {
    health: (o = {}) => request("GET", "/api/health", { signal: o.signal }),
    search: (body, o = {}) => request("POST", "/api/search", { body, signal: o.signal }),
    getTrack: (id, o = {}) => request("GET", `/api/tracks/${enc(id)}`, { signal: o.signal }),
    getNeighbors: (id, o = {}) =>
      request("GET", `/api/tracks/${enc(id)}/neighbors`, { query: { k: o.k }, signal: o.signal }),
    submitFeedback: (body, o = {}) => request("POST", "/api/feedback", { body, signal: o.signal }),
    getSession: (id, o = {}) => request("GET", `/api/sessions/${enc(id)}`, { signal: o.signal }),
    getMapMeta: (o = {}) => request("GET", "/api/map/meta", { signal: o.signal }),
    getMapPoints: (query = {}, o = {}) => request("GET", "/api/map/points", { query, signal: o.signal }),
    resolveUrl: (path) => resolveUrl(path),
  };
}

function networkError(cause: unknown, signal: AbortSignal | undefined): ApiClientError {
  const aborted = signal?.aborted || (cause instanceof DOMException && cause.name === "AbortError");
  if (aborted) {
    return new ApiClientError({
      kind: "aborted",
      code: "aborted",
      message: "The request was cancelled.",
      status: null,
      details: {},
    });
  }
  return new ApiClientError({
    kind: "network",
    code: "network_error",
    message: "The server could not be reached.",
    status: null,
    details: { cause: cause instanceof Error ? cause.message : String(cause) },
  });
}

function httpError(response: Response, text: string): ApiClientError {
  try {
    const body = JSON.parse(text) as { error?: { code?: unknown; message?: unknown; details?: unknown } };
    const error = body.error;
    if (error && typeof error.code === "string" && typeof error.message === "string") {
      const details = error.details && typeof error.details === "object" ? error.details : {};
      return new ApiClientError({
        kind: "http",
        code: error.code,
        message: error.message,
        status: response.status,
        details: details as Record<string, unknown>,
      });
    }
  } catch {
    // not an envelope; fall through
  }
  return new ApiClientError({
    kind: "http",
    code: `http_${response.status}`,
    message: response.statusText || `Request failed with status ${response.status}.`,
    status: response.status,
    details: {},
  });
}

/** The client the hooks use by default. */
export const apiClient: ApiClient = createApiClient();
