// Stable keys for deck.gl `updateTriggers`. Accessors are recomputed when a key changes, so a key
// must change exactly when the inputs do: the same ids in a different Set object give the same
// key, and ids in a different order too.

/** FNV-1a, 32 bit: short keys for large id sets. */
function hash(text: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(36);
}

/** Key of an id set, independent of identity and order; `""` for an empty or absent set. */
export function setKey(ids: Iterable<string> | null | undefined): string {
  if (!ids) return "";
  const sorted = [...new Set(ids)].sort();
  return sorted.length === 0 ? "" : `${sorted.length}:${hash(sorted.join("\n"))}`;
}

export interface TriggerInputs {
  selected?: Iterable<string> | null;
  highlighted?: Iterable<string> | null;
  hovered?: string | null;
  dimUnhighlighted?: boolean;
  /** Changes when the theme or the genre scale changes. */
  themeKey: string;
}

/** Per-accessor trigger keys for the ScatterplotLayer. */
export function triggerKeys(i: TriggerInputs) {
  const state = [setKey(i.selected), setKey(i.highlighted), i.hovered ?? "", i.dimUnhighlighted ? "dim" : ""].join("|");
  return {
    getFillColor: `${state}|${i.themeKey}`,
    getRadius: state,
    getLineColor: `${state}|${i.themeKey}`,
    getLineWidth: state,
  };
}
