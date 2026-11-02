// The Discover screen's zones (ui.md §3). The map fills the viewport behind everything; search,
// results, controls and the status pill float over it, and only their own boxes take pointer
// events so the map stays draggable between them.
// - ≥ 1024 px (Tailwind `lg`): search top-centre, results panel on the left above the map
//   controls, status pill bottom-right, details drawer on the right (rendered by its own Sheet).
// - < 1024 px: search pinned at the top; results become a bottom sheet (rendered by
//   ResultsPanel itself, outside these zones), the status pill sits under the search, and the
//   controls sit above the sheet's peek height.
import { useMemo, useSyncExternalStore, type ReactNode } from "react";

/** Same width as Tailwind's `lg` breakpoint (64rem = 1024 px), used by the `lg:` classes below. */
export const DESKTOP_QUERY = "(min-width: 64rem)";

function subscribe(query: string) {
  return (onChange: () => void) => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
    const list = window.matchMedia(query);
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  };
}

/** Desktop layout or sheets. Without `matchMedia` (tests, very old browsers) the desktop layout. */
export function useIsDesktop(): boolean {
  const sub = useMemo(() => subscribe(DESKTOP_QUERY), []);
  return useSyncExternalStore(
    sub,
    () => (typeof window.matchMedia === "function" ? window.matchMedia(DESKTOP_QUERY).matches : true),
    () => true,
  );
}

export interface DiscoverLayoutProps {
  /** The map canvas (or its fallback): fixed, full-bleed, behind everything. */
  map: ReactNode;
  /** Search bar, chips and the clarification prompt. */
  search: ReactNode;
  /** The desktop results panel; on small screens the container passes the sheet in `overlays`. */
  results?: ReactNode;
  /** Map controls, legend and caption. */
  controls?: ReactNode;
  /** Degraded-mode pill. */
  status?: ReactNode;
  /** Things that position themselves: the details drawer, the mobile results sheet. */
  overlays?: ReactNode;
  /** The polite live region's text. */
  announcement: string;
}

export function DiscoverLayout({ map, search, results, controls, status, overlays, announcement }: DiscoverLayoutProps) {
  return (
    <div className="relative h-dvh w-full overflow-hidden bg-surface-canvas text-fg">
      <div className="fixed inset-0">{map}</div>

      <main aria-label="Discover music" className="pointer-events-none fixed inset-0 flex flex-col gap-2 p-2 lg:p-3">
        <div className="mx-auto flex w-full max-w-80 flex-col gap-1">
          <div className="pointer-events-auto flex flex-col gap-1">{search}</div>
          {/* below the search on small screens; bottom-right on desktop */}
          {status && <div className="pointer-events-auto self-start lg:fixed lg:right-3 lg:bottom-3">{status}</div>}
        </div>
        <div className="flex min-h-0 flex-1 flex-col items-start justify-end gap-1">
          {results && <div className="pointer-events-auto flex min-h-0 flex-1 flex-col">{results}</div>}
          {controls && <div className="pointer-events-auto mb-12 flex flex-col items-start gap-1 lg:mb-0">{controls}</div>}
        </div>
      </main>

      {overlays}

      <p aria-live="polite" aria-atomic="true" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}
