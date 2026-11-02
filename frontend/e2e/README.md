# e2e/: Playwright, mock mode by default

`npm run e2e` starts `vite --mode mock` and runs every spec against the MSW contract mocks.

| Spec | What |
|---|---|
| `flows.spec.ts` | The five core flows of ui.md §5 (idle, search, explore, refine, free browse) × every mock scenario. Flows that can't apply in a scenario (no results to refine, no map to browse) are skipped by name. |
| `discover.spec.ts` | Feedback and refinement details; map ⇄ list selection with a real canvas click. |
| `a11y.spec.ts` | axe on every scenario × desktop/phone × dark/light, the keyboard walkthrough, contrast over the map. See `docs/ui/accessibility.md`. |
| `visual.spec.ts` | Screenshot baselines (`__screenshots__/`) of key states × dark/light × 1280/390 px. |
| `contract-harness.spec.ts` | The dev-only hook harness (P09.T09). |
| `real-backend.spec.ts` | Opt-in smoke against a running backend (below). |

Shared helpers are in `helpers.ts`. Map points are clicked at the screen position the camera fit implies, so map tests run with `reducedMotion: "reduce"` (instant camera).

**Visual baselines.** Change them deliberately: `npx playwright test e2e/visual.spec.ts --update-snapshots`, then review the images in the diff. A 1 % pixel tolerance absorbs anti-aliasing in the software-rendered WebGL canvas. When CI fails, the diffs and traces are uploaded as the `playwright-results` artifact.

**Real backend.** `make serve` in the repo root, then
`E2E_REAL_BACKEND=1 API_PROXY_TARGET=http://127.0.0.1:8000 npm run e2e`. Only the real-backend specs run; the mock-mode specs are skipped.
