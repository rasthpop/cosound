// The interpreted query as chips (ui.md §4.1, ux-states-and-evidence §2). The UI never edits the
// spec: soft chips emit typed attribute feedback, and everything else is read-only. Hard
// constraints come with "Edit your search", the only way to change them (D1).
import { PencilLine } from "lucide-react";

import type { FeedbackType, InterpretedQuery, Preference } from "@/api/types";
import { ICON } from "@/theme/tokens/semantic";

import { hardConstraintLabel, vocalPreferenceLabel } from "../format/labels";
import { Button } from "../ui/button";
import { QueryChip } from "./QueryChip";

export interface AttributeFeedback {
  eventType: Extract<FeedbackType, "MORE_OF_ATTRIBUTE" | "LESS_OF_ATTRIBUTE">;
  /** The preference category (`mood`, `instrument`, …, `vocals`). */
  attribute: string;
  /** The term within the category (`chill`); `null` for vocals. */
  value: string | null;
}

export interface QueryChipsProps {
  query: InterpretedQuery;
  /** `capabilities.llm_interpreter === "fallback"`: show a subtle note. */
  interpreterFallback?: boolean;
  onAttributeFeedback: (feedback: AttributeFeedback) => void;
  onEditQuery?: () => void;
}

/** Soft preference fields in display order, with their feedback category. */
const PREFERENCE_FIELDS = [
  ["instrument_preferences", "instrument"],
  ["mood_preferences", "mood"],
  ["genre_preferences", "genre"],
  ["energy_preferences", "energy"],
  ["tempo_preferences", "tempo"],
  ["texture_preferences", "texture"],
  ["era_preferences", "era"],
] as const satisfies ReadonlyArray<readonly [keyof InterpretedQuery, string]>;

export function QueryChips({ query, interpreterFallback = false, onAttributeFeedback, onEditQuery }: QueryChipsProps) {
  const soft: { key: string; label: string; attribute: string; value: string | null }[] = [];
  for (const [field, attribute] of PREFERENCE_FIELDS) {
    for (const p of query[field] as Preference[]) soft.push({ key: `${attribute}:${p.value}`, label: p.value, attribute, value: p.value });
  }
  // required/excluded vocals are hard constraints, shown below; preferred/avoided are soft
  const vocals = query.vocal_preferences === "preferred" || query.vocal_preferences === "avoided" ? vocalPreferenceLabel(query.vocal_preferences) : null;
  const hasHard = query.hard_constraints.length > 0;
  const empty = soft.length === 0 && !vocals && !hasHard && query.negative_preferences.length === 0;

  return (
    <section aria-label="What the search understood" className="flex flex-col gap-0.5">
      {!empty && (
        <ul className="flex flex-wrap items-center gap-0.5">
          {soft.map((chip) => (
            <li key={chip.key}>
              <QueryChip
                kind="soft"
                label={chip.label}
                onMore={() => onAttributeFeedback({ eventType: "MORE_OF_ATTRIBUTE", attribute: chip.attribute, value: chip.value })}
                onLess={() => onAttributeFeedback({ eventType: "LESS_OF_ATTRIBUTE", attribute: chip.attribute, value: chip.value })}
              />
            </li>
          ))}
          {vocals && (
            <li>
              <QueryChip
                kind="soft"
                label={vocals}
                moreLabel="More vocals"
                lessLabel="Fewer vocals"
                onMore={() => onAttributeFeedback({ eventType: "MORE_OF_ATTRIBUTE", attribute: "vocals", value: null })}
                onLess={() => onAttributeFeedback({ eventType: "LESS_OF_ATTRIBUTE", attribute: "vocals", value: null })}
              />
            </li>
          )}
          {query.hard_constraints.map((c) => (
            <li key={`hard:${c.attribute}:${c.operator}:${c.value ?? ""}:${(c.range ?? []).join("-")}`}>
              <QueryChip kind="hard" label={hardConstraintLabel(c)} />
            </li>
          ))}
          {query.negative_preferences.map((p) => (
            <li key={`neg:${p.value}`}>
              <QueryChip kind="negative" label={p.value} />
            </li>
          ))}
          {hasHard && onEditQuery && (
            <li>
              <Button size="sm" variant="quiet" onClick={onEditQuery}>
                <PencilLine aria-hidden="true" {...ICON} />
                Edit your search
              </Button>
            </li>
          )}
        </ul>
      )}
      {query.uncertainties.length > 0 && (
        <ul className="flex flex-col text-meta text-muted">
          {query.uncertainties.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      )}
      {interpreterFallback && <p className="text-meta text-muted">Read by the built-in parser instead of the language model.</p>}
    </section>
  );
}
