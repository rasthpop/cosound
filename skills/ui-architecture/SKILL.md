---
name: ui-architecture
description: Frontend architecture for the music discovery interface — the View/Hook/Container pattern, what each frontend folder may contain and import, prop/event contracts for views, state ownership, and how the visual layer stays swappable without touching hooks, the API client, or the backend. Load before writing or reviewing any React code in frontend/src/components/, pages/, theme/, or when deciding where frontend logic belongs.
---

# UI Architecture

Spec: `base.md` §14, §3 (rules), §1 req. 10 ("no dependence on any particular visual style, color palette, or layout"). The concrete look & feel comes from the separate UI/UX plan; this skill defines the frame it must fit into.

## 1. Three roles

```
 hooks/ (functional track)          pages/ = containers (UI track)          components/ = views (UI track)
 ─────────────────────────          ──────────────────────────────          ─────────────────────────────
 useMusicSearch()      ──state──▶   <DiscoverPage>                ──props──▶ <TrackPlate results=… />
 useTrackFeedback()    ◀─calls───     wires hooks → views,        ◀─events── onFeedback(trackId, type)
 useMusicMap()                        owns UI-only state                     <TrackMap points=… onTrackSelect=… />
 useTrackDetails()                    (open panels, focus, layout)           <TrackDetail detail=… />
```

- **Hooks** (owned by P09) talk to the API client and expose `{data, status, error, actions}`. They contain no JSX, no styling, no deck.gl.
- **Containers** (`pages/`) are the only place hooks are called. They translate hook state into view props and view events into hook actions. They own **UI-only state** (which panel is open, hover, layout mode, animation flags) — never domain state (results, sessions, scores).
- **Views** (`components/`) are pure: `props → markup`, callbacks out. No `fetch`, no hooks from `hooks/`, no API client, no global stores. They may hold trivial local UI state (an open/closed toggle).

The checker (`skills/music-discovery-architecture/scripts/check_boundaries.py --only ts`) enforces the imports; review enforces the rest.

## 2. Folder contract

```
frontend/src/
├── api/          # functional — client.ts, types.ts, generated.ts
├── hooks/        # functional — the 4 hooks + small shared utilities
├── mocks/        # functional — fixtures + MSW handlers (UI develops against these)
├── theme/        # UI — tokens, theme provider, global styles
├── components/   # UI — views; components/map/ is the only deck.gl location
│   ├── map/
│   ├── plate/ track/ search/ feedback/ …   (names decided by the UI plan)
├── pages/        # UI — containers / routes
├── App.tsx main.tsx   # composition root
```

## 3. View contracts

- Props use API types from `api/types.ts` **or** narrower view-model types declared next to the view (`type TrackCardProps = Pick<TrackResult, "title" | "artists" | …>`). Prefer narrow `Pick`s — they make views reusable against fixtures and keep refactors local.
- Events are named for user intent, carry IDs not objects: `onTrackSelect(trackId)`, `onFeedback({trackId, eventType, attribute?})`, `onQuerySubmit(text)`, `onLoadMore()`.
- Views never compute relevance, sort by score, filter by constraints, or derive "is this a flute track". They may **format** (round a score for display, join artist names, pick a label for an enum) — formatting helpers live in `components/format/` and are unit-tested.
- Every view that renders server data must handle the full state set (see `ux-states-and-evidence`).

## 4. State ownership

| State | Owner |
|---|---|
| results, session, interpreted query, warnings, capabilities | `useMusicSearch` |
| feedback submission status, refreshed plate | `useTrackFeedback` (+ `useMusicSearch.refresh`) |
| map points, filters, pagination, selected track ids | `useMusicMap` |
| track details cache | `useTrackDetails` |
| hover, focus, panel layout, camera/view state of the map, animations | containers / map view |
| theme / color mode / density | `theme/` provider |

No global store is introduced unless the UI plan needs cross-page state; if it does, it holds UI state only and lives under `pages/` or `theme/`.

## 5. Styling isolation

- Visual values come **only** from tokens (`ui-design-tokens`). No hex colors, pixel magic numbers, or font names inside components.
- The styling technology (CSS modules, vanilla-extract, Tailwind, styled-components…) is the UI plan's choice; whatever it is, it lives in `theme/` + `components/` and nothing under `hooks/`/`api/` may depend on it.
- Swapping the whole visual layer = replacing `theme/`, `components/`, `pages/`. That is the acceptance test for isolation (U05).

## 6. Review checklist

- [ ] No import of `hooks/` or `api/client` from `components/`.
- [ ] No deck.gl outside `components/map/`.
- [ ] No sorting/filtering/scoring of results in views or containers beyond what the API returned (display order = API order).
- [ ] No literal colors/sizes; tokens only.
- [ ] Every server-data view has loading/empty/error/degraded states.
- [ ] Events carry IDs and typed enums from `api/types.ts`.
