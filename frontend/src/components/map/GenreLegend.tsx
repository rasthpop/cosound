// Genre legend (ui.md §4.3) from `MapMeta.genres`, with counts and the map's genre colours. A
// click isolates one genre (`onGenreFilter(genre)`); clicking it again shows all (`null`). The
// "Other" fold and points without a genre are listed but not filterable: the API filters by a
// named genre only. Hidden when the API sent no genre summary.
import type { GenreCount } from "@/api/types";
import { genreScale } from "@/theme/scales/categorical";
import { useTheme } from "@/theme/useTheme";

import { cn } from "../ui/cn";

export interface GenreLegendProps {
  genres: readonly GenreCount[] | null | undefined;
  /** The genre currently filtered to; `null` = all. */
  activeGenre: string | null;
  onGenreFilter: (genre: string | null) => void;
}

const NAMES = { other: "Other genres", none: "No genre" } as const;

export function GenreLegend({ genres, activeGenre, onGenreFilter }: GenreLegendProps) {
  const { tokens } = useTheme();
  if (!genres || genres.length === 0) return null;
  const { legend } = genreScale(genres, tokens);
  return (
    <section aria-label="Genre legend" className="flex w-30 flex-col gap-0.5 rounded-lg border border-hairline bg-surface-panel p-1 backdrop-blur-panel">
      <h2 className="px-0.5 text-meta text-muted">Genres</h2>
      <ul className="flex flex-col">
        {legend.map((entry) => {
          const swatch = (
            <span aria-hidden="true" className="size-1 shrink-0 rounded-pill" style={{ background: entry.color }} />
          );
          const count = (active: boolean) => (
            <span className={cn("ml-auto tabular-nums", active ? "text-fg" : "text-muted")}>{entry.count}</span>
          );
          if (entry.kind !== "genre" || entry.genre === null) {
            return (
              <li key={entry.kind} className="flex items-center gap-1 px-0.5 py-0.5 text-meta">
                {swatch}
                <span className="text-muted">{NAMES[entry.kind === "other" ? "other" : "none"]}</span>
                {count(false)}
              </li>
            );
          }
          const active = activeGenre === entry.genre;
          const genre = entry.genre;
          return (
            <li key={genre}>
              <button
                type="button"
                aria-pressed={active}
                onClick={() => onGenreFilter(active ? null : genre)}
                className={cn(
                  "flex w-full cursor-pointer items-center gap-1 rounded-sm px-0.5 py-0.5 text-left text-meta hover:bg-surface-raised",
                  active && "bg-accent-subtle font-medium",
                  activeGenre !== null && !active && "text-muted",
                )}
              >
                {swatch}
                <span>{genre}</span>
                {count(active)}
              </button>
            </li>
          );
        })}
      </ul>
      {activeGenre !== null && (
        <button type="button" onClick={() => onGenreFilter(null)} className="cursor-pointer px-0.5 text-left text-meta text-fg underline underline-offset-4">
          Show all genres
        </button>
      )}
    </section>
  );
}
