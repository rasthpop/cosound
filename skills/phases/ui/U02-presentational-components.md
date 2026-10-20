# U02 — Presentational Views & State Variants *(provisional)*

**Goal:** all non-map views as pure components (props in, typed events out), each with every applicable state, built and verified against contract fixtures — no backend required.
**Depends on:** U01, P09.T02

### U02.T01 — Primitives & formatting helpers
- **Skills:** ui-architecture, ui-design-tokens
- **Depends on:** U01.T02
- **Files:** frontend/src/components/primitives/*, frontend/src/components/format/*.ts(+tests)
- **Do:**
  - Base building blocks required by the UI plan (buttons, chips, badges, panels, text styles) using tokens only; formatters (artist list, duration, enum labels, match-strength band labels — no percentages).
- **Done when:**
  - Stories for each primitive in all themes; formatter unit tests incl. null handling.
- **Status:** [ ]

### U02.T02 — Search input & interpreted-query view
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U02.T01
- **Files:** frontend/src/components/search/*
- **Do:**
  - Query entry (`onQuerySubmit`), interpreted query: soft preferences, hard constraints, negatives visually distinct; chip interactions emit typed feedback intents; clarification prompt variant.
- **Done when:**
  - Stories: idle, typing, interpreted (soft/hard/negative), needs-clarification; tests for emitted events.
- **Status:** [ ]

### U02.T03 — Track result card & plate
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U02.T01
- **Files:** frontend/src/components/plate/*, frontend/src/components/track/TrackCard*
- **Do:**
  - Card shows title, artists, description, match reasons, evidence status, uncertainty flags, links only when non-null; plate renders in API order with loading/stale/empty/no-confident-match/degraded variants.
- **Done when:**
  - Stories from fixtures for every state; tests: nulls absent, no re-sorting, no percentage text, `onTrackSelect`/`onFeedback` payloads typed.
- **Status:** [ ]

### U02.T04 — Feedback controls
- **Skills:** ux-states-and-evidence, ui-architecture
- **Depends on:** U02.T03
- **Files:** frontend/src/components/feedback/*
- **Do:**
  - Gestures mapped 1:1 to the 7 feedback types; attribute picker for WRONG_INSTRUMENT / *_OF_ATTRIBUTE; per-track pending state; "what changed" summary view.
- **Done when:**
  - Tests: each gesture emits the correct event type; pending/rejected states; change summary renders from fixture.
- **Status:** [ ]

### U02.T05 — Track detail view
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U02.T01
- **Files:** frontend/src/components/track/TrackDetail*
- **Do:**
  - Metadata, release/artist info, links, audio-analysis availability, relationships, neighbors (labeled as audio-embedding neighbors), coordinates presence; loading/error/no-audio variants.
- **Done when:**
  - Stories for detail, no-audio detail, error; a11y check passes.
- **Status:** [ ]

### U02.T06 — System state views
- **Skills:** ux-states-and-evidence
- **Depends on:** U02.T01
- **Files:** frontend/src/components/states/*
- **Do:**
  - Reusable error (by `error.code`), offline, degraded-capability banners (semantic/map/LLM), empty and idle states per the UI plan's tone.
- **Done when:**
  - Story per state; copy reviewed against `ux-states-and-evidence` (no overclaiming).
- **Status:** [ ]

## Exit criteria
- [ ] Every non-map view exists as a pure component with all state stories; `check_boundaries.py --only ts` green; no literal visual values.
