// The audio match band of a result (`TrackResult.match_strength`): "Strong match" or "Partial
// match" as words with a token-coloured mark. Weak and missing bands show nothing; the band is
// never a number or a percentage.
import type { MatchStrength } from "@/api/types";

import { matchBandLabel } from "../format/labels";
import { cn } from "../ui/cn";

export function MatchBand({ band }: { band: MatchStrength | null | undefined }) {
  const text = matchBandLabel(band);
  if (!text) return null;
  return (
    <span className="inline-flex items-center gap-0.5 text-meta text-fg">
      <span aria-hidden="true" className={cn("size-1 rounded-pill", band === "strong" ? "bg-match-strong" : "bg-match-partial")} />
      {text}
    </span>
  );
}
