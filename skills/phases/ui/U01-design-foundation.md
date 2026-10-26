# U01 — Design Foundation: Tokens, Tailwind Theme, Workbench

**Goal:** encode the visual language in `ui.md` §2 as swappable tokens that Tailwind v4 consumes through CSS variables, and set up shadcn/ui, Storybook and the UI checks (ADR-0003), before any view is built.
**Depends on:** U00, P00.T04

### U01.T01 — Token architecture & primitives
- **Skills:** ui-design-tokens, ui-architecture, dataviz
- **Depends on:** U00.T04, P00.T04
- **Files:** frontend/src/theme/tokens/{primitives,semantic,components,types}.ts, frontend/src/theme/tokens/tokens.test.ts, docs/ui/visual-reference.md
- **Do:**
  - Primitives from ui.md §2: near-black canvas `#0B0B0F`, glass surface `rgba(18,18,24,0.72)` + 12 px blur, hairline border, radius 12–16 px, one accent (violet `#A78BFA` default), type sizes 13/15/20/28, weights 400/500, Inter, 8 px grid, row height ~56 px, durations 150/250/600 ms ease-out.
  - Semantic families from `ui-design-tokens` §3 (surface.canvas/panel/raised, text.default/muted, border.hairline, focus.ring, state.*, evidence.*, match.strong/partial/weak, feedback.*, map.point.*, motion.* including reduced), with a typed `SemanticTokens` contract. Dark theme is the default, light is optional.
  - Check the Subwave reference ("See the shape of your library") and record what was matched in `docs/ui/visual-reference.md`. Adjust values only, never structure.
- **Done when:**
  - Both themes `satisfies SemanticTokens`; text/surface pairs meet WCAG AA, including text on the glass panel over the darkest and lightest map backdrop (test).
- **Status:** [ ]

### U01.T02 — Tailwind v4 wiring, token CSS emitter & ThemeProvider
- **Skills:** ui-design-tokens, ui-architecture
- **Depends on:** U01.T01
- **Files:** frontend/scripts/emit-tokens.mjs, frontend/src/theme/generated/tokens.css, frontend/src/theme/global.css, frontend/src/theme/ThemeProvider.tsx, frontend/src/theme/useTheme.ts, frontend/src/theme/ThemeProvider.test.tsx, frontend/vite.config.ts, frontend/package.json
- **Do:**
  - `@tailwindcss/vite`; `npm run tokens` emits per-theme CSS variables and a `@theme inline` block mapping utilities to semantic variables, with the default namespaces reset (ADR-0003). `npm run tokens:check` fails on a diff and runs in CI.
  - `ThemeProvider` sets `data-theme` on `<html>`, follows `prefers-color-scheme` only when no theme was chosen, and exposes `reducedMotion` from `prefers-reduced-motion`. `@fontsource-variable/inter` is imported in `global.css`.
- **Done when:**
  - Test: switching theme changes only the `data-theme` attribute and the computed CSS variables; reduced motion is respected; `bg-red-500` does not compile to a rule (default palette reset); `tokens:check` green.
- **Status:** [ ]

### U01.T03 — Map data-viz scales
- **Skills:** ui-design-tokens, deckgl-track-map, dataviz
- **Depends on:** U01.T01
- **Files:** frontend/src/theme/scales/{categorical,pointStates,toRgba}.ts, frontend/src/theme/scales/*.test.ts
- **Do:**
  - A categorical genre scale of 8–10 muted, desaturated hues. It is deterministic by genre name (not by load order), so colors stay stable across filters and pages. `null` genre maps to a neutral grey token, never a category.
  - Point-state styles from ui.md §2: default 2–4 px at ~0.55 opacity, dimmed ~0.15, result 6–8 px + light ring, selected = accent ring + pulse, hover. Selection never differs by color alone.
  - `toRgba` returns `[r, g, b, a]` tuples for deck.gl.
- **Done when:**
  - Unit tests for determinism, the `null` mapping and RGBA output; dataviz contrast and color-vision-deficiency check against `#0B0B0F` documented in the test file header.
- **Status:** [ ]

### U01.T04 — shadcn/ui, Storybook & UI checks
- **Skills:** ui-isolated-development, ui-architecture, music-discovery-architecture
- **Depends on:** U01.T02, P09.T02
- **Files:** frontend/components.json, frontend/src/components/ui/cn.ts, frontend/.storybook/*, frontend/src/theme/Tokens.stories.tsx, frontend/scripts/check-visual-literals.mjs, frontend/package.json, frontend/eslint.config.js, frontend/playwright.config.ts, skills/music-discovery-architecture/scripts/check_boundaries.py, skills/music-discovery-architecture/SKILL.md
- **Do:**
  - Run `shadcn init` with aliases into `components/ui/` (no `lib/`).
  - Storybook 10 (`@storybook/react-vite`) with `addon-a11y`, `addon-themes` (toolbar sets `data-theme`), `msw-storybook-addon` and `addon-vitest`. The token gallery story covers every theme.
  - `check-visual-literals.mjs` bans hex/rgb/hsl and Tailwind arbitrary values in `components/` and `pages/`, and runs from `npm run lint`.
  - Boundary checker: radix-ui/vaul/motion/lucide-react/cva/clsx/tailwind-merge allowed under `components/` only (script and skill change together).
  - `@axe-core/playwright` installed for e2e.
- **Done when:**
  - `npm run storybook`, `npm run test-storybook` (vitest addon) and `npm run e2e` run; token gallery renders in both themes with zero axe violations; boundary check green; the literal check fails on a planted `bg-[#fff]` (test).
- **Status:** [ ]

## Exit criteria
- [ ] Tokens and themes encode ui.md §2; Tailwind resolves only to tokens; workbench and checks ready; zero literal visual values outside `theme/`.
