# UI glossary

Names from [`ui.md`](../../skills/phases/ui/ui.md), each with the component or file it becomes. Code, stories and tests use these names.

| Plan term | Component / file | Meaning |
|---|---|---|
| Discover screen | `pages/DiscoverPage.tsx` | The single screen: map canvas plus floating surfaces. |
| Map canvas | `components/map/TrackMap.tsx` | Full-bleed deck.gl renderer of the UMAP projection (`OrthographicView` + `ScatterplotLayer`). |
| Map controls | `components/map/MapControls.tsx` | Zoom ±, reset view, legend toggle, list-alternative toggle (bottom-left). |
| Genre legend | `components/map/GenreLegend.tsx` | Collapsible list of genres with their colors, used as a filter. Entries come from data. |
| Map caption | `components/map/MapCaption.tsx` | "Positions come from audio similarity (CLAP + UMAP). Nearness is suggestive, not exact." |
| Map tooltip | `components/map/MapTooltip.tsx` | Hover card: title · artist · genre. On touch it is a compact card in the sheet. |
| List alternative | `components/map/MapPointList.tsx` | Keyboard and screen-reader list of the same points. Also the WebGL fallback. |
| Map fallback | `components/map/MapFallback.tsx` | Calm empty field: "Map is unavailable — search still works." |
| Search bar | `components/search/SearchBar.tsx` | Floating input with submit arrow, progress line, example queries and the Refine toggle. |
| Example queries | `components/search/ExampleQueries.tsx` | 3–4 clickable suggestions. The copy lives in `pages/`. |
| Interpreted-query chips | `components/search/QueryChips.tsx` | What the system understood: soft, hard (lock) and negative chips. |
| Chip | `components/search/QueryChip.tsx` | One preference or constraint, with an optional More/Less menu. |
| Clarification prompt | `components/search/ClarificationPrompt.tsx` | `clarification_question` and a reply field, under the bar. |
| Results panel | `components/results/ResultsPanel.tsx` | Left floating panel (desktop), bottom sheet (< 1024 px): header, change strip, list, states. |
| Result row | `components/results/ResultRow.tsx` | rank · title · artists · badges · match band · evidence note · play · feedback. |
| Match band | `components/results/MatchBand.tsx` | "Strong match" / "Partial match" from `match_strength`. Never a percentage. |
| Evidence note | `components/results/EvidenceNote.tsx` | e.g. "Matched on catalog data only", "Vocals not verified". |
| Not-on-map marker | `components/results/NotOnMapMarker.tsx` | Results without coordinates in the current projection. |
| What-changed strip | `components/feedback/ChangeStrip.tsx` | Dismissible summary of `changes` / `change_summary` after feedback. |
| Feedback actions | `components/feedback/FeedbackActions.tsx` | More like this · Less like this · Not relevant (+ Wrong instrument… in the drawer). |
| Instrument picker | `components/feedback/InstrumentPicker.tsx` | Popover for `WRONG_INSTRUMENT`, fed from the interpreted query. |
| Mini-player | `components/audio/MiniPlayer.tsx` | Inline play/pause for a row. One track plays at a time. |
| Audio player | `components/audio/AudioPlayer.tsx` | Full-width player in the drawer: native `<audio>` with shadcn controls. |
| Details drawer | `components/track/TrackDetailsDrawer.tsx` | Right sheet (desktop), full-height sheet (< 1024 px). |
| Score bands | `components/track/ScoreBands.tsx` | Collapsed by default: semantic / metadata / relationship as bands; `null` → "not available". |
| Nearby in sound | `components/track/NeighborList.tsx` | Neighbors from `/neighbors`, labeled by `metric`. They are not map distances. |
| Status pill | `components/states/StatusPill.tsx` | Bottom-right, only when degraded or offline. |
| State views | `components/states/*` | Empty, no confident match, error (by `error.code`), offline. |
| Primitives | `components/ui/*` | shadcn/ui copies (Button, Input, Badge, Tooltip, Popover, Sheet, Drawer, ScrollArea, Toggle, Separator, Skeleton). |
| Plate | — | The ranked result set of one search turn (`SearchResponse.results`). |
| Free browse | — | Exploring the map with no query. Clicking a point opens details. |
