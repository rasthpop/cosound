# U01 — Design Foundation: Tokens, Theme, Workbench *(provisional)*

**Goal:** encode the UI plan's visual system as swappable tokens and themes, and set up the component workbench and UI test tooling, before any view is built.
**Depends on:** U00, P00.T04

### U01.T01 — Token architecture & primitives
- **Skills:** ui-design-tokens, ui-architecture
- **Depends on:** U00.T04, P00.T04
- **Files:** frontend/src/theme/tokens/{primitives,semantic,components}.ts, frontend/src/theme/tokens/types.ts
- **Do:**
  - Primitive scales from the UI plan (color, type, space, radius, elevation, motion, density); semantic token families from the skill (surface, text, state, evidence, match, feedback, map.point, motion incl. reduced); typed `SemanticTokens` contract.
- **Done when:**
  - Each theme `satisfies SemanticTokens`; no component exists yet that bypasses tokens.
- **Status:** [ ]

### U01.T02 — Theme provider, color modes & global styles
- **Skills:** ui-design-tokens
- **Depends on:** U01.T01
- **Files:** frontend/src/theme/ThemeProvider.tsx, frontend/src/theme/global.css, frontend/src/theme/useTheme.ts
- **Do:**
  - CSS custom properties emission, theme/atmosphere switching, `prefers-color-scheme` and `prefers-reduced-motion` handling, font loading per ADR.
- **Done when:**
  - Switching theme changes CSS variables only (test); reduced-motion respected.
- **Status:** [ ]

### U01.T03 — Data-viz scales for the map
- **Skills:** ui-design-tokens, deckgl-track-map, dataviz
- **Depends on:** U01.T01
- **Files:** frontend/src/theme/scales/{categorical,sequential,toRgba}.ts, frontend/src/theme/scales/*.test.ts
- **Do:**
  - Genre categorical scale (+ "other"), match-strength sequential scale, RGBA conversion for deck.gl; contrast & color-vision-deficiency checks against the map background.
- **Done when:**
  - Unit tests for scale determinism and RGBA output; contrast check documented.
- **Status:** [ ]

### U01.T04 — Component workbench & UI test tooling
- **Skills:** ui-isolated-development
- **Depends on:** U01.T02, P09.T02
- **Files:** frontend/.storybook/* (or Ladle config), frontend/playwright.config.ts, frontend/src/theme/Tokens.stories.tsx
- **Do:**
  - Workbench with theme switcher and MSW integration; Playwright configured for mock mode; axe a11y checks; token gallery story.
- **Done when:**
  - `npm run storybook` and `npm run e2e` run; token gallery renders in every theme.
- **Status:** [ ]

## Exit criteria
- [ ] Tokens/themes encode the UI plan; workbench and test tooling ready; zero literal visual values outside `theme/`.
