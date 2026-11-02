// Static copy owned by the Discover screen (ui.md §4.1): example queries and the live-region
// announcements. Views stay copy-free where the container decides the wording.
import type { SearchResponse } from "@/api/types";

/** Shown under the empty, focused search bar. Plain descriptions the parser understands. */
export const EXAMPLE_QUERIES = [
  "something chill with a flute",
  "energetic electronic for a run",
  "melancholic piano without vocals",
  "warm acoustic folk",
] as const;

/** "12 results for “chill flute”" — what the polite live region says after a search. */
export function announceSearch(response: Pick<SearchResponse, "outcome" | "results" | "clarification_question">, query: string): string {
  if (response.outcome === "needs_clarification") {
    return response.clarification_question ? `The search needs more detail: ${response.clarification_question}` : "The search needs more detail.";
  }
  if (response.outcome === "no_confident_match") return `No confident match for “${query}”`;
  const n = response.results.length;
  if (n === 0) return `No results for “${query}”`;
  return `${n} ${n === 1 ? "result" : "results"} for “${query}”`;
}

export const ANNOUNCE_SEARCHING = "Searching…";
