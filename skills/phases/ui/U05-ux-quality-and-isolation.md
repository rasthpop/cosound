# U05 — UX Quality, Accessibility & Isolation Proof

**Goal:** verify that the interface meets ui.md §6–§7 and the project's honesty rules, and prove the visual layer can be swapped without touching the functional system.
**Depends on:** U04

### U05.T01 — Accessibility audit
- **Skills:** ux-states-and-evidence, ui-isolated-development
- **Depends on:** U04.T05
- **Files:** frontend/e2e/a11y.spec.ts, docs/ui/accessibility.md
- **Do:**
  - Axe on every scenario and on desktop + mobile viewports.
  - Keyboard-only walkthrough of ui.md §7: `/` → input → results → feedback → details → map list alternative.
  - Check the live-region announcements, focus loop and return in the drawer, and contrast of text on glass panels over the densest map area in both themes. Selection must not rely on color alone, and reduced motion must stop the pulse and camera easing.
- **Done when:**
  - No serious/critical axe violations; the walkthrough is scripted in e2e and documented.
- **Status:** [ ]

### U05.T02 — Visual regression & e2e flows
- **Skills:** ui-isolated-development
- **Depends on:** U04.T05
- **Files:** frontend/e2e/*.spec.ts, frontend/e2e/__screenshots__/
- **Do:**
  - Screenshot baselines for key stories and scenarios per theme and at 1280 px and 390 px widths.
  - E2E for the five core flows in ui.md §5 across all mock scenarios. An optional `slow` smoke against the real backend (fma_small).
- **Done when:**
  - CI runs e2e in mock mode; baselines committed.
- **Status:** [ ]

### U05.T03 — Evidence & copy audit
- **Skills:** ux-states-and-evidence, grounded-explanations
- **Depends on:** U04.T05
- **Files:** docs/ui/copy-audit.md
- **Do:**
  - Run the `evidence-auditor` agent over UI copy, tooltips, labels, the map caption and the fixtures.
  - Verify: no percentages or probabilities; bands only from the API; no implied instrument detection; honest map labeling ("nearness is suggestive"); neighbors labeled by metric; nulls absent; FMA attribution and per-track license shown with playback.
- **Done when:**
  - The audit has zero unresolved findings.
- **Status:** [ ]

### U05.T04 — Performance pass
- **Skills:** deckgl-track-map, ui-architecture
- **Depends on:** U04.T05
- **Files:** docs/ui/performance.md
- **Do:**
  - Map at 8k (fma_small), 10k and 100k synthetic points: pan/zoom frame rate, highlight update latency, page-in. Render counts on refinement and hover (no per-frame React state).
  - Production bundle against the ADR-0003 budget (≤ 600 kB gzip JS).
- **Done when:**
  - Budgets met or deviations documented with a follow-up.
- **Status:** [ ]

### U05.T05 — Visual-layer isolation proof
- **Skills:** ui-isolated-development, music-discovery-architecture
- **Depends on:** U05.T02
- **Files:** docs/ui/isolation-check.md
- **Do:**
  - On a throwaway branch, replace `theme/`, `components/` and `pages/` with a minimal alternative skin (or switch to a radically different theme). Then run the backend tests, hook tests, contract check and boundary check.
- **Done when:**
  - All functional checks pass unchanged; the result is recorded (base §1 requirement 10, §14.4).
- **Status:** [ ]

## Exit criteria
- [ ] Accessibility, visual regression, copy honesty, performance and isolation verified.
