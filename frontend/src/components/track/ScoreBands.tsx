// Per-signal bands for the open track (ui.md §4.4 "Score breakdown"), collapsed by default.
// `null` means the signal was not computed and reads "not available", never 0. No numbers.
import type { ScoreBands as ScoreBandsData } from "@/api/types";

import { bandLabel } from "../format/labels";

const SIGNALS = [
  ["semantic", "Sound"],
  ["metadata", "Catalog data"],
  ["relationship", "Catalog relationships"],
] as const satisfies ReadonlyArray<readonly [keyof ScoreBandsData, string]>;

export function ScoreBands({ bands }: { bands: ScoreBandsData }) {
  return (
    <details className="group rounded-md border border-hairline px-1 py-0.5 text-meta">
      <summary className="cursor-pointer text-muted group-open:text-fg">How it matched</summary>
      <dl className="mt-0.5 flex flex-col">
        {SIGNALS.map(([key, name]) => (
          <div key={key} className="flex gap-1.5">
            <dt className="w-15 shrink-0 text-muted">{name}</dt>
            <dd>{bandLabel(bands[key])}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
