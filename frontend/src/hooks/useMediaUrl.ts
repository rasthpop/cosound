// A playable URL for an API media path such as `TrackResult.preview_url`, so views and
// containers never import the API client. `null` in gives `null` out: no clip, no URL.
import { useMemo } from "react";

import { apiClient, type ApiClient } from "../api/client";

export interface UseMediaUrlOptions {
  client?: ApiClient;
}

export function useMediaUrl(path: string | null, options: UseMediaUrlOptions = {}): string | null {
  const client = options.client ?? apiClient;
  return useMemo(() => (path === null ? null : client.resolveUrl(path)), [client, path]);
}
