// Text formatters for API values. They format; they never decide or invent meaning.
// - `null`/empty input returns `null`, and the view renders nothing (missing is not zero).
// - There is no percentage formatter: scores are shown as bands, never as numbers.
import type { Artist } from "@/api/types";

/** Readable text for a code this UI has no label for: `some_new_flag` → "Some new flag". */
export function humanize(code: string): string {
  const words = code.replace(/[_:]+/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : code;
}

/** "Artist A, Artist B"; `null` when there are none. */
export function formatArtists(artists: ReadonlyArray<Pick<Artist, "name">> | null | undefined): string | null {
  const names = (artists ?? []).map((a) => a.name.trim()).filter(Boolean);
  return names.length ? names.join(", ") : null;
}

/** "3:07" or "1:02:05"; `null` for a missing or invalid duration. */
export function formatDuration(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return null;
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** "No tracks", "1 track", "12 tracks". */
export function formatResultCount(count: number): string {
  if (count === 0) return "No tracks";
  return count === 1 ? "1 track" : `${count} tracks`;
}
