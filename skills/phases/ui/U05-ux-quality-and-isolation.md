# U05 — UX Quality, Accessibility & Isolation Proof *(provisional)*

**Goal:** verify the interface meets the UI plan's quality bar and the project's honesty rules, and prove the visual layer is swappable without touching the functional system.
**Depends on:** U04

### U05.T01 — Accessibility audit
- **Skills:** ux-states-and-evidence, ui-isolated-development
- **Depends on:** U04.T05
- **Files:** frontend/e2e/a11y.spec.ts, docs/ui/accessibility.md
- **Do:**
  - Axe on every screen/state; keyboard-only walkthrough (search → results → feedback → details → map alternative); screen-reader announcements; contrast per theme.
- **Done when:**
  - No serious/critical axe violations; keyboard walkthrough documented.
- **Status:** [ ]

### U05.T02 — Visual regression & e2e flows
- **Skills:** ui-isolated-development
- **Depends on:** U04.T05
- **Files:** frontend/e2e/*.spec.ts, frontend/e2e/__screenshots__/
- **Do:**
  - Screenshot baselines for key stories per theme; e2e flows for all mock scenarios; optional slow e2e against the real backend with the 20-track corpus.
- **Done when:**
  - CI runs e2e in mock mode; baselines committed.
- **Status:** [ ]

### U05.T03 — Evidence & copy audit
- **Skills:** ux-states-and-evidence, grounded-explanations
- **Depends on:** U04.T05
- **Files:** docs/ui/copy-audit.md
- **Do:**
  - Run the `evidence-auditor` agent over UI copy, tooltips, labels and fixtures; verify no percentages/probabilities, no implied instrument detection, honest map labeling, nulls rendered as absent.
- **Done when:**
  - Audit has zero unresolved findings.
- **Status:** [ ]

### U05.T04 — Performance pass
- **Skills:** deckgl-track-map, ui-architecture
- **Depends on:** U04.T05
- **Files:** docs/ui/performance.md
- **Do:**
  - Map with large synthetic datasets, interaction latency, bundle size budget from the UI plan, render counts on refinement.
- **Done when:**
  - Budgets met or deviations documented.
- **Status:** [ ]

### U05.T05 — Visual-layer isolation proof
- **Skills:** ui-isolated-development, music-discovery-architecture
- **Depends on:** U05.T02
- **Files:** docs/ui/isolation-check.md
- **Do:**
  - On a throwaway branch, replace `theme/`, `components/`, `pages/` with a minimal alternative skin (or a radically different theme); run backend tests, hook tests, contract check, boundary check.
- **Done when:**
  - All functional checks pass unchanged; result recorded (base §1 requirement 10, §14.4).
- **Status:** [ ]

## Exit criteria
- [ ] Accessibility, visual regression, copy honesty, performance, and isolation verified.
