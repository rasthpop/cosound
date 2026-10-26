# ADR-0003: UI stack

- **Status:** Proposed. It becomes Accepted when the U00 PR is merged by the project owner.
- **Date:** 2026-10-26
- **Phase/Task:** U00.T03

## Context

The UI/UX plan (`skills/phases/ui/ui.md` §8) prefers ready-made libraries: shadcn/ui on Radix, Tailwind CSS v4, deck.gl, vaul, lucide-react, motion, self-hosted Inter, and Storybook or Ladle. The project rules are fixed regardless of the plan:

- `base.md` §1 req. 10 and §14.4: the visual layer (`theme/`, `components/`, `pages/`) must be replaceable without touching hooks, the API client or the backend.
- `ui-architecture`: views are pure, containers are the only hook callers, deck.gl lives only in `components/map/`.
- `ui-design-tokens`: components consume semantic tokens only; themes remap semantic → primitive; a theme switch changes CSS variables only; zero literal colors or sizes outside `theme/`.
- Existing frontend: React 19.3, Vite 8, TypeScript 6, vitest 4, Playwright 1.64, MSW 2.

Versions below are the current releases on 2026-10-26, and each declares compatibility with React 19 and Vite 8.

## Decision

| Need | Choice | Version |
|---|---|---|
| Styling | Tailwind CSS v4 via `@tailwindcss/vite`, themed only through token CSS variables | `tailwindcss` 4.3 |
| Primitives | shadcn/ui components copied into `components/ui/` (unified `radix-ui` package), restyled with semantic tokens | `shadcn` CLI 4.22, `radix-ui` 1.8 |
| Mobile sheets | vaul through the shadcn `Drawer` | `vaul` 1.1 |
| Map | deck.gl `@deck.gl/react` + `core` + `layers`: `OrthographicView` + `ScatterplotLayer`, WebGL2 | 9.4 |
| Icons | `lucide-react`, 16 px, stroke 1.5 | 1.61 |
| Panel motion | `motion` (`motion/react`) for panel enter/exit only, under `<MotionConfig reducedMotion="user">`. Camera moves use deck.gl transitions. | 14.6 |
| Audio | native `<audio>` with shadcn controls | — |
| Font | `@fontsource-variable/inter`, imported in `theme/global.css`, self-hosted (no font CDN) | 5.3 |
| Workbench | **Storybook** (`@storybook/react-vite`) with `addon-a11y`, `addon-themes`, `msw-storybook-addon` and `addon-vitest` | 10.6 |
| A11y in e2e | `@axe-core/playwright` | 4.14 |
| Routing | none: one screen. `App.tsx` keeps serving the dev-only `/__dev/harness`. | — |

### How tokens reach Tailwind

1. The source of truth is TypeScript: `theme/tokens/{primitives,semantic,components}.ts`, with every theme `satisfies SemanticTokens`.
2. `npm run tokens` emits `theme/generated/tokens.css`. It contains one block of CSS custom properties per theme (`:root[data-theme="dark"]`, `…="light"`, dark is the default) and a Tailwind `@theme inline` block that maps utilities to **semantic** variables only (`--color-surface: var(--color-surface-base)`). The default Tailwind namespaces are reset (`--color-*: initial`, and the same for font, radius, shadow and easing), so `bg-red-500` or `text-xl` simply do not exist. `npm run tokens:check` fails on a diff, like `contract:check`.
3. `ThemeProvider` switches themes by setting `data-theme` on `<html>`, so a switch changes CSS variables only. deck.gl reads colors through `theme/scales/toRgba.ts`, never by parsing CSS in `components/map/`.
4. Arbitrary values (`bg-[#…]`, `p-[13px]`) and hex/rgb/hsl literals are banned in `components/` and `pages/` by `scripts/check-visual-literals.mjs`, which runs in `npm run lint`. Spacing uses the token grid (`--spacing: 8px`-based steps from the tokens).

### shadcn in this repo

- `components.json` aliases `ui` → `@/components/ui` and `utils` → `@/components/ui/cn`. There is no `lib/` folder, because every file belongs to a layer in the boundary table.
- Generated components are edited to use semantic utilities (`bg-surface-raised`, `border-hairline`, `text-muted`). shadcn's default palette variables are not used.

### Boundary checker additions (made in U01.T04)

`TS_THIRD_PARTY` gains `radix-ui`, `@radix-ui/`, `vaul`, `motion`, `lucide-react`, `class-variance-authority`, `clsx` and `tailwind-merge` → `components/` only. deck.gl stays at `components/map/`. `hooks/`, `api/` and `mocks/` can import none of them. The script and the architecture skill change in the same commit.

### Storybook over Ladle

Storybook has maintained add-ons for exactly the checks this plan requires: axe on every story, a theme toolbar that sets `data-theme`, MSW per story for container stories, and running stories as vitest tests. Ladle would need each of these hand-built. Stories are already excluded from the boundary checker (`.stories.tsx`).

## Consequences

- Everything visual is replaceable by swapping `theme/`, `components/` and `pages/`. No library here is importable from `hooks/` or `api/`, and the checker enforces that.
- Tailwind class strings in components are the only styling surface. Because the default scales are reset, every class resolves to a token, which keeps "zero literal visual values" checkable with a script instead of review.
- shadcn components are owned code. Updates are manual diffs, the price of being able to restyle them fully.
- New dev dependencies: Storybook (heavy, dev only), Tailwind, axe. The production bundle adds Radix, vaul, motion, lucide (tree-shaken) and deck.gl (~ the largest). Budget: ≤ 600 kB gzip total JS for the production build, checked in U05.T04.
- Desktop details drawer: a non-modal Radix Dialog. The map stays usable with the pointer, Tab cycles inside the drawer while focus is in it (FocusScope loop), and Esc/✕ return focus to the originating row or point. On < 1024 px the sheet is modal. This interprets ui.md §7 "focus is trapped in the open drawer" without making the map inert on desktop.

## Reversible by

Replacing Tailwind or shadcn touches `theme/` and `components/` only. The token TS source and `SemanticTokens` contract survive, and only the emitter changes. Ladle could replace Storybook by porting `*.stories.tsx`, which is CSF in both. deck.gl is contained in `components/map/` behind the `TrackMap` props contract.
