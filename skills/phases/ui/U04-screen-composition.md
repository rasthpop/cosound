# U04 — Containers & Screen Composition *(provisional)*

**Goal:** wire hooks to views in containers that own only UI state, composing the screens and layouts described in the UI plan.
**Depends on:** U02, U03, P09.T08

### U04.T01 — Discovery screen container
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U02.T02, U02.T03, U02.T06, P09.T04, P09.T08
- **Files:** frontend/src/pages/DiscoverPage.tsx (name per UI plan), frontend/src/pages/DiscoverPage.test.tsx
- **Do:**
  - `useMusicSearch` → search input, interpreted query, plate, state views; layout zones and responsive behavior from the UI plan.
- **Done when:**
  - MSW-backed tests for happy, empty, no-confident-match, clarification, degraded-semantic, error scenarios.
- **Status:** [ ]

### U04.T02 — Feedback wiring
- **Skills:** ui-architecture, ux-states-and-evidence
- **Depends on:** U04.T01, U02.T04, P09.T05
- **Files:** frontend/src/pages/DiscoverPage.tsx, frontend/src/pages/feedback.ts
- **Do:**
  - View feedback events → `useTrackFeedback.submit` with refresh; refreshed plate + change summary; pending states per track.
- **Done when:**
  - E2E (mock): feedback produces refreshed plate and visible "what changed".
- **Status:** [ ]

### U04.T03 — Map panel & selection sync
- **Skills:** ui-architecture, deckgl-track-map
- **Depends on:** U04.T01, U03.T02, P09.T07
- **Files:** frontend/src/pages/MapPanel.tsx (name per UI plan)
- **Do:**
  - `useMusicMap` → TrackMap; highlight current results; plate selection ⇄ map selection ⇄ details in sync; results without coordinates listed as "not on the map"; map-down keeps search usable.
- **Done when:**
  - E2E (mock): select on map opens details; select in plate highlights on map; map-down scenario leaves search functional.
- **Status:** [ ]

### U04.T04 — Track detail panel
- **Skills:** ui-architecture
- **Depends on:** U02.T05, P09.T06
- **Files:** frontend/src/pages/TrackDetailPanel.tsx
- **Do:**
  - `useTrackDetails` → TrackDetail; focus management on open/close; neighbors navigation.
- **Done when:**
  - Tests: open/close focus behavior, neighbor click selects that track.
- **Status:** [ ]

### U04.T05 — App shell, routing & retire the contract harness
- **Skills:** ui-architecture
- **Depends on:** U04.T01, U04.T03, U04.T04, P09.T09
- **Files:** frontend/src/App.tsx, frontend/src/main.tsx, frontend/src/dev/README.md
- **Do:**
  - Compose screens per the UI plan; routing if required; keep `dev/ContractHarness` dev-only or remove it.
- **Done when:**
  - Production build contains no dev harness; all container tests and e2e pass.
- **Status:** [ ]

## Exit criteria
- [ ] Hooks are called only in `pages/`; views remain pure; display order equals API order.
