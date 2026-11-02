# Visual-layer isolation check

U05.T05, 2026-11-02. This checks base §1 requirement 10 (the interface depends on no particular
visual style) and §14.4 (the visual layer can be replaced without touching the functional system).

## Method

On a throwaway branch (`u05-isolation-check`, in a separate git worktree, deleted afterwards),
created from `07af2d3`:

1. **Deleted the whole visual layer:** `frontend/src/theme/`, `frontend/src/components/`,
   `frontend/src/pages/`, the Storybook config, and the UI E2E specs and screenshot baselines.
2. **Wrote a minimal alternative skin:**
   - `theme/ThemeProvider.tsx` passes children through (no tokens, no theming).
   - `theme/global.css` is one serif rule.
   - `components/Plain.tsx` has a plain form and a plain `<table>`.
   - `pages/DiscoverPage.tsx` calls the same hooks (`useMusicSearch`, `useTrackFeedback`,
     `useMusicMap`, `useTrackDetails`) and shows the map as a point count, with no deck.gl.
   - A one-story Storybook config.
3. **Ran every functional check without editing anything else.** `main.tsx`, `App.tsx`, `hooks/`,
   `api/`, `mocks/`, `vite.config.ts` and the whole backend were byte-identical to the base commit.
   The changed paths were only `frontend/src/{components,pages,theme}`, `frontend/.storybook` and
   `frontend/e2e` (UI specs).

## Result

| Check | Command | Result |
|---|---|---|
| Backend tests | `pytest -m "not slow"` (from the worktree's `src/`) | **1077 passed**, 1 skipped (live LLM) |
| OpenAPI and fixtures in sync | `export_openapi.py --check`, `export_fixtures.py --check` | pass |
| Generated TS types match the schema | `npm run contract:check` | pass |
| Boundary checker | `check_boundaries.py` | pass |
| Typecheck of the whole frontend with the new skin | `tsc --noEmit` | pass |
| Hook, API-client and mock tests, plus `App.test.tsx` | `vitest --project unit src/hooks src/api src/mocks src/App.test.tsx test` | **97 passed** (11 files) |
| Production build and bundle check | `npm run build` | pass (no mocks, no harness in the bundle) |
| Hook-level E2E (contract harness, mock mode) | `playwright test e2e/contract-harness.spec.ts` | 3 passed |

**All functional checks pass unchanged.** The only coupling between the composition root and the
skin is two names: `ThemeProvider` (from `theme/`) and `DiscoverPage` (from `pages/`). A
replacement skin provides them, and nothing else has to change.

## Notes

- `App.test.tsx` passed with the new skin because it asserts only a `search` landmark and a `main`
  named "Discover music". It belongs to the composition root, not to either skin.
- `vite.config.ts` loads the Storybook plugin for its `storybook` test project. Vitest evaluates it
  for every project, so a replacement skin needs at least a minimal `.storybook/main.ts`. That
  config is part of the visual layer's tooling. Splitting the Storybook project out of
  `vite.config.ts` would remove even that dependency. It's a possible follow-up, not a coupling to
  the functional system.
- `tokens:check` (design tokens) and the story tests belong to the visual layer and were replaced
  along with it, so they weren't part of this check.
