// The always-visible caption (ui.md §4.3): what positions mean, and that nearness is a hint.
export const MAP_CAPTION = "Positions come from audio similarity (CLAP + UMAP). Nearness is suggestive, not exact.";

export function MapCaption() {
  return <p className="max-w-60 text-meta text-muted">{MAP_CAPTION}</p>;
}
