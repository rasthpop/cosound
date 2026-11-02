// The results panel (ui.md §4.2, §3): a header with the query echo, the count and a collapse
// toggle; a slot for the change strip; and a scrolling body. On desktop it is the left floating
// panel; below 1024 px the container renders it as a vaul bottom sheet (`variant="sheet"`)
// snapping at peek / half / full. The body is whatever the container passes: the ranked list,
// or one of the state views.
import { ChevronDown, ChevronUp } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { ICON, SHEET_SNAP_POINTS } from "@/theme/tokens/semantic";

import { formatResultCount } from "../format/text";
import { Button } from "../ui/button";
import { Drawer, DrawerContent, DrawerDescription, DrawerTitle } from "../ui/drawer";
import { ScrollArea } from "../ui/scroll-area";
import { Skeleton } from "../ui/skeleton";

export interface ResultsPanelProps {
  /** The query as the user typed it (`interpreted_query.original_query`). */
  query: string | null;
  /** Number of results; `null` while there is no plate (loading the first one, errors). */
  count: number | null;
  /** The body is from an earlier query while a new one runs. */
  stale?: boolean;
  /** "What changed" after feedback (ChangeStrip). */
  changeStrip?: ReactNode;
  children: ReactNode;
  variant?: "panel" | "sheet";
  /** Sheet only: start at this snap point index (0 = peek). */
  initialSnap?: 0 | 1 | 2;
}

function Header({
  query,
  count,
  titleId,
  stale = false,
  collapsed,
  onToggle,
}: {
  query: string | null;
  count: number | null;
  titleId: string;
  stale?: boolean;
  collapsed?: boolean;
  onToggle?: () => void;
}) {
  return (
    <header className="flex items-start gap-1 px-2 pt-1.5 pb-1">
      <div className="flex min-w-0 flex-1 flex-col">
        <h2 id={titleId} className="text-body font-medium">
          {count === null ? "Results" : formatResultCount(count)}
        </h2>
        {query && <p className="truncate text-meta text-muted">for “{query}”</p>}
        {/* stale results stay readable: marked in words, not dimmed below AA contrast */}
        {stale && (
          <p role="status" className="text-meta text-muted">
            Updating — these are the previous results
          </p>
        )}
      </div>
      {onToggle && (
        <Button size="icon-sm" variant="quiet" aria-expanded={!collapsed} aria-label={collapsed ? "Show results" : "Hide results"} onClick={onToggle}>
          {collapsed ? <ChevronDown aria-hidden="true" {...ICON} /> : <ChevronUp aria-hidden="true" {...ICON} />}
        </Button>
      )}
    </header>
  );
}

export function ResultsPanel({ query, count, stale = false, changeStrip, children, variant = "panel", initialSnap = 1 }: ResultsPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [snap, setSnap] = useState<number | string | null>(SHEET_SNAP_POINTS[initialSnap]);
  const titleId = useId();
  const body = (
    <div aria-busy={stale} className="flex min-h-0 flex-1 flex-col">
      {changeStrip}
      <ScrollArea className="min-h-0 flex-1">
        <div className="px-1 pb-1">{children}</div>
      </ScrollArea>
    </div>
  );

  if (variant === "sheet") {
    return (
      <Drawer open modal={false} dismissible={false} snapPoints={[...SHEET_SNAP_POINTS]} activeSnapPoint={snap} setActiveSnapPoint={setSnap}>
        <DrawerContent aria-describedby={undefined} className="flex flex-col">
          <DrawerTitle className="sr-only">{count === null ? "Results" : formatResultCount(count)}</DrawerTitle>
          {query && <DrawerDescription className="sr-only">for “{query}”</DrawerDescription>}
          <Header query={query} count={count} titleId={titleId} stale={stale} />
          {body}
        </DrawerContent>
      </Drawer>
    );
  }

  return (
    <section
      aria-labelledby={titleId}
      className="flex max-h-full w-47.5 flex-col rounded-lg border border-hairline bg-surface-panel text-fg backdrop-blur-panel"
    >
      <Header query={query} count={count} titleId={titleId} stale={stale} collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      {!collapsed && body}
    </section>
  );
}

/** The ranked list: rows in API order, never re-sorted. */
export function ResultsList({ children, label = "Ranked results" }: { children: ReactNode; label?: string }) {
  return (
    <ol aria-label={label} className="flex flex-col gap-0.5">
      {children}
    </ol>
  );
}

/** The first search is running and there is no plate yet: row-shaped placeholders, no layout jump. */
export function ResultsLoading({ rows = 4 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading results" className="flex flex-col gap-0.5">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex min-h-7 gap-1 px-1 py-1">
          <Skeleton className="h-2 w-2" />
          <div className="flex flex-1 flex-col gap-0.5">
            <Skeleton className="h-2 w-3/5" />
            <Skeleton className="h-1.5 w-2/5" />
          </div>
        </div>
      ))}
    </div>
  );
}
