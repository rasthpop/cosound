# UI / UX Plan — Semantic Music Discovery

> Input for the `ui-plan-intake` skill. This document fixes **how the interface looks and behaves**.
> It does not change backend semantics. Wherever it names data, it names an existing API/hook
> field. Anything missing is flagged as a **contract request**, never a UI workaround.

**Visual reference:** Subwave, *"See the shape of your library"*
(https://www.getsubwave.com/news/see-the-shape-of-your-library). The idea we take from it: the
library itself, drawn as a calm field of points, is the main surface. Typography and chrome stay
quiet so the map carries the page.
*Note:* the reference page could not be fetched while this plan was written. The visual traits
below describe the intended feel. Check them against the page and adjust tokens (not structure)
if they differ.

---

## 1. Design principles

1. **The map is the canvas.** The UMAP projection fills the viewport. Everything else (search, results, details) floats on top of it as light, translucent surfaces.
2. **Minimal chrome.** One input, one results panel, one details drawer. No nav bar, no sidebars full of filters, no dashboards.
3. **Quiet until asked.** In the idle state you see the map and the input. Panels appear only when they have content.
4. **Search and space are one action.** A query lights up its results on the map, and selecting in the list and selecting on the map are the same event.
5. **Honest by default.** Follow `ux-states-and-evidence`: no invented values, no percentage scores, and every degraded state is visible.
6. **Use ready components and don't hand-roll primitives.** Every interactive primitive (input, popover, drawer, tooltip, toggle, scroll area) comes from the component library chosen in §8.

## 2. Visual language

| Aspect | Direction |
|---|---|
| Mode | **Dark-first** (deep near-black canvas, e.g. `#0B0B0F`), with an optional light mode through tokens only. |
| Map points | Small soft dots (2–4 px), low opacity (~0.55), additive feel. Clusters read as glowing "constellations" because of density, with no hulls or outlines. |
| Point color | Muted categorical scale by `MapPoint.genre` (8–10 hues, desaturated). `null` genre → neutral grey token (never assigned a fake category). |
| Highlight | Search results: full opacity, larger radius (6–8 px), thin light ring. All other points dim to ~0.15 opacity. Selected track: accent ring plus a slow pulse (disabled under `prefers-reduced-motion`). |
| Surfaces | Floating panels: translucent dark (`rgba(18,18,24,0.72)`) with `backdrop-filter: blur(12px)`, 1 px hairline border, 12–16 px radius, no heavy shadows. |
| Typography | One sans family (Inter or Geist via `@fontsource`). Sizes: 13 / 15 / 20 / 28. Weights 400 / 500 only. Track titles 15/500, metadata 13/400 in a muted token. |
| Accent | One accent color (e.g. soft violet `#A78BFA` or teal, chosen at token time), used only for focus, selection and the primary action. |
| Iconography | `lucide-react`, 16 px, 1.5 stroke. Icons support text and never replace it. |
| Motion | 150–250 ms ease-out for panels, and 600 ms camera fly-to on the map. All motion respects `prefers-reduced-motion`. |
| Density | Generous whitespace: 8 px spacing grid, results rows ~56 px tall. |

All values above are encoded as **tokens** in `frontend/src/theme/` (primitive → semantic → component), following `ui-design-tokens`. Views never hard-code colors.
## 3. Layout

### Desktop (≥ 1024 px)

```
┌──────────────────────────────────────────────────────────────────────┐
│                         [  Search input bar  ]   ← top-center, floats │
│                         [ interpreted-query chips ]                   │
│                                                                      │
│  ┌───────────────┐                                                   │
│  │ Results panel │          UMAP MAP (full-bleed canvas)             │
│  │  (left, 380px)│                                                   │
│  │  ranked list  │              · ·  ·:·.  ·                         │
│  │               │            ·:·:::·  ·.·:·                ┌───────┐│
│  │               │                ·  ·::·:·                │Details││
│  │               │                                         │drawer ││
│  └───────────────┘                                         │(right)││
│  [legend · zoom · reset]                  [status / degraded pill]   │
└──────────────────────────────────────────────────────────────────────┘
```

- **Map:** `position: fixed; inset: 0`. Always behind everything else.
- **Search bar:** top-center, max-width 640 px, 24 px from the top.
- **Results panel:** left, 380 px wide, top below the search bar, bottom 24 px. Collapsible.
- **Details drawer:** right, 400 px wide, opens on selection and closes with Esc or ✕.
- **Map controls:** bottom-left (zoom +/−, reset view, legend toggle).
- **Status pill:** bottom-right, shown only for degraded states.

### Tablet / mobile (< 1024 px)

- Map stays full-bleed and the search bar is pinned at the top.
- The results panel becomes a **bottom sheet** with three snap points (peek 96 px / half / full).
- The details drawer becomes a full-height sheet over the results sheet.
- Hover interactions become tap interactions, and the tooltip turns into a compact card inside the sheet.

## 4. Components

### 4.1 Search input bar

- One text input, with placeholder "Describe a sound… e.g. *something chill with a flute*".
- Submit with Enter or the arrow button. Esc clears focus. `/` focuses the input from anywhere.
- When the input is empty and focused, show 3–4 **example queries** as clickable suggestions (static copy in `pages/`).
- While a search runs: a thin indeterminate progress line on the bottom edge of the bar. The previous results stay visible, marked stale.
- Below the bar: **interpreted-query chips** from `SearchResponse.interpreted_query` (instruments, moods, genres, energy, tempo, …). Soft preferences, hard constraints (solid outline + lock icon) and negatives (strikethrough or "not" prefix) look different. Removing a chip sends `LESS_OF_ATTRIBUTE` through `useTrackFeedback`. The UI never edits the spec locally.
- If `outcome = "needs_clarification"`: show `clarification_question` inline under the bar, with a reply field.
- Data: `useMusicSearch().search(query)`, `status`, `data.interpreted_query`, `data.outcome`.

### 4.2 Results panel

- Header: query echo plus the result count ("12 tracks"), and a collapse toggle.
- A ranked list in **API order**, never re-sorted on the client. Each row shows:
  - rank · **title** · artists (comma-joined `artists[].name`)
  - genre tags (`genres`, `styles`) as small muted badges
  - a match strength band ("Strong match" / "Partial match") derived from `match_reasons` / bands, **never a raw percentage**
  - evidence note when relevant (`evidence_status`, `uncertainty_flags`), e.g. "Matched on catalog data only"
  - a play button only when `preview_url` is non-null (inline mini-player, one track at a time)
  - hover reveals feedback actions: 👍 More like this (`MORE_LIKE_THIS`), 👎 Less like this (`LESS_LIKE_THIS`), ✕ Not relevant (`NOT_RELEVANT`)
- Hovering a row highlights its point on the map. Clicking a row selects the track: the map flies to it and the details drawer opens.
- Results with no `spatial` coordinates carry a small "not on map" marker.
- After feedback: a dismissible strip at the top lists `change_summary` ("what changed"), and the original query stays visible.
- Empty, no-confident-match and error states use the copy and actions from `ux-states-and-evidence` §1.
- Data: `useMusicSearch().data.results`, `useTrackFeedback().submit`.
### 4.3 Interactive UMAP map

Built with **deck.gl** (`OrthographicView` + `ScatterplotLayer`), confined to `frontend/src/components/map/` per the `deckgl-track-map` skill. It is a pure renderer: it takes points and emits events, and it never fetches data or computes similarity.

| Interaction | Behavior |
|---|---|
| Pan / zoom | Drag, wheel, pinch and double-click zoom. Inertia is on. Zoom range is clamped to the projection bounds (`map_meta.bounds`). |
| Hover | Tooltip with title · artist · genre (from `MapPoint` fields only). The cursor becomes a pointer. |
| Click | Selects the track (`SELECT_TRACK` and opening details). The camera eases to the point. The same state as selecting a row. |
| Search highlight | On a new result set, highlight result points, dim the rest, and fit the camera to the bounds of the results (padding 80 px, 600 ms). |
| Reset | The "Reset view" control or `0` key fits all points and clears the highlight but keeps the results list. |
| Legend | A collapsible genre legend. Clicking a genre filters the visible points via `useMusicMap` filters (`genre`). Clicking again resets. |
| Filter | Optional toggle "Only tracks with audio" → `has_audio` filter. |
| Keyboard | Arrow keys pan, `+`/`−` zoom, Tab moves into the results list. An accessible **list alternative** (`MapPointList`) is available from the controls. |

- An always-visible caption under the legend: *"Positions come from audio similarity (CLAP + UMAP). Nearness is suggestive, not exact."*
- Loading: points fade in as pages arrive (`useMusicMap` pagination).
- Map unavailable (`capabilities.map = "unavailable"` or 503): the canvas shows a calm empty field with the message "Map is unavailable — search still works." Search is not affected.
- WebGL failure: fall back to `MapPointList`.
- Data: `useMusicMap()` → `points`, `meta`, `selectedTrackIds`, `select/deselect/clear`, `filters`. The search highlight comes from `SearchResponse.results[].spatial` / `track_id`.

### 4.4 Details drawer

- Title, artists, genres and styles, plus the license and FMA credit next to playback.
- Full-width audio player when `preview_url` exists. Otherwise: "No audio preview available."
- `description` and `match_reasons` exactly as returned. Nothing is shown when they are empty.
- Score breakdown (optional, collapsed by default): semantic / metadata / relationship as **bands**. `null` → "not available", never 0.
- **Nearby in sound:** neighbors from `GET /api/tracks/{id}/neighbors` (`useTrackDetails`). Each neighbor is clickable and selects that track on the map.
- "Open on FMA" link only when `source_url` is non-null (`rel="noopener noreferrer"`).
- Feedback: More / Less like this, Not relevant, and "Wrong instrument…" (attribute picker fed from the interpreted query).
- Data: `useTrackDetails(trackId)`.

### 4.5 Status pill

Bottom-right, shown only when something is degraded:
- `semantic = "unavailable"` → "Sound-based matching is off — catalog data only"
- `map = "unavailable"` → "Map unavailable"
- network / offline → "Offline — retry", which keeps the typed query

## 5. Core flows

1. **Idle:** full map (all points, genre colors, softly dimmed), input focused, example queries visible.
2. **Search:** type → Enter → progress line → chips appear → results panel slides in → result points light up → camera fits to them.
3. **Explore:** hover rows or points (they cross-highlight) → click → camera flies there → details drawer opens → browse neighbors → click a neighbor → repeat.
4. **Refine:** 👍/👎 on a row, or remove a chip → plate refreshes from the server → "what changed" strip → map highlight updates.
5. **Free browse:** no query. Pan around the map, click any point → details drawer (search results panel stays hidden).

## 6. States (all required as workbench stories)

Idle · loading · refreshing (stale) · ok · empty · no confident match · needs clarification · degraded semantic · degraded map · LLM fallback (silent / subtle note in chips) · error · offline · WebGL failure · track without audio · track without coordinates.
Fixtures already exist in `frontend/src/mocks/fixtures/` for most of these.

## 7. Accessibility

- A full keyboard path: `/` → input → results → feedback → details → map list alternative.
- `aria-live="polite"` region announces "12 results for …" and refinement changes.
- Focus is trapped in the open drawer and returns to the originating row or point on close.
- WCAG AA contrast through tokens, checked on translucent panels over the map. Selection is never shown by color alone (ring + size).
- `prefers-reduced-motion`: no pulse, instant camera moves.

## 8. Technology (ready-made libraries)

| Need | Library |
|---|---|
| Component primitives | **shadcn/ui** (Radix UI primitives, copied into `components/ui/`): Input, Button, Badge, Tooltip, Popover, Sheet (drawer + mobile bottom sheet), ScrollArea, Toggle, Separator, Skeleton |
| Styling | **Tailwind CSS v4**, with theme tokens exposed as CSS variables from `frontend/src/theme/` |
| Map | **deck.gl** (`@deck.gl/react`, `@deck.gl/core`, `@deck.gl/layers`): `OrthographicView` + `ScatterplotLayer` |
| Bottom sheet (mobile) | **vaul** (shadcn Drawer) |
| Icons | **lucide-react** |
| Motion | **motion** (Framer Motion) for panel transitions only. Map camera transitions use deck.gl's built-in transitions. |
| Audio | Native `<audio>` with custom shadcn controls (no heavy player library) |
| Fonts | `@fontsource-variable/inter` (or Geist), self-hosted |
| Workbench | **Storybook** (or Ladle). Final pick goes in the UI stack ADR. |

Rules: deck.gl imports only under `components/map/`. Views consume hooks and `api/types.ts` only (`ui-architecture`). The ADR for this stack is written during intake (`docs/adr/00xx-ui-stack.md`).

## 9. Open questions / possible contract requests

- **Cluster labels on the map** (e.g. naming regions "Ambient", "Folk") would need server-side cluster summaries → **contract request** if desired. The UI must not compute them. MVP: no region labels, only the genre legend.
- **Result match band:** confirm whether the API exposes a semantic band field, or whether bands come only from `match_reasons`. If neither works, raise a contract request rather than bucketing `score` on the client.
- **Free-text feedback** ("more like this but faster") from the input while results are shown: supported by `submit({freeText})`. Confirm the input bar should route follow-up text to feedback rather than a new search (proposal: a "Refine" toggle next to the input).
