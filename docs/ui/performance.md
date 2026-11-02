# Performance pass — Discover screen

U05.T04, measured 2026-11-02. Machine: Linux, headless Chromium (Playwright). **WebGL in this
environment is SwiftShader**, so the GPU work runs on the CPU, which matters for the frame-rate
numbers below.

```bash
cd frontend
PERF=1 npx playwright test e2e/perf.spec.ts                       # synthetic 10k / 100k (mock)
PERF=1 E2E_REAL_BACKEND=1 API_PROXY_TARGET=http://127.0.0.1:8000 \
  npx playwright test e2e/perf.spec.ts                            # fma_small via `make serve`
```

## Budgets

| Budget | Target | Measured | Status |
|---|---|---|---|
| Production JS, gzip (ADR-0003) | ≤ 600 kB | **348 kB** (main chunk 299 kB; deck.gl is most of it) | met |
| fma_small map page-in | — | **2.2 s** for 7,993 points | good |
| Search → results highlighted on the real map | — | **2.6 s**, backend search included | good |
| No per-frame React state; render counts | — | Hover: 1 small `TrackMap` commit per pointer move (tooltip position); the point layer is reused. Refinement: 8 page commits | met (now a test) |
| Pan/zoom frame rate | smooth | 8 / 17 fps on fma_small, **software WebGL** | not measurable here; see below |

## Map

| Dataset | Page-in | Pan | Zoom | Selection repaint |
|---|---|---|---|---|
| fma_small, real backend (7,993) | 2.2 s | 8 fps | 17 fps | 2.3 s* |
| 10k synthetic (mock) | 2.7 s | 7 fps | 7 fps | 2.4 s* |
| 100k synthetic (mock) | 48 s | (not measured) | (not measured) | 6.2 s* |

\* From the click until two frames have painted after it. That includes opening the details
drawer, the camera move and the software rendering of those frames.

### What limits the frame rate here

A CPU profile of a 10k-point pan (20 pointer moves, 12.2 s) shows **11.9 s in `(program)`**, which
is native rendering: SwiftShader rasterizing the canvas. The app's own JavaScript took under 200 ms
of it, and 169 ms of that is `readPixels` for hover picking. Frame rate falls with point count only
because of software rasterization: 54 fps at 5 points, 41 fps at 1k, 7.6 fps at 10k. Removing the
panels' `backdrop-filter` made no difference (7.5 vs 7.0 fps). A selection at 10k spends about 50 ms
in JavaScript, 8 ms of it in the point-style accessors; the rest is rendering.

So the measurements here bound the app's own work, which is small, and can't show frame rate on real
hardware. **Follow-up:** measure pan/zoom frame rate once in a headed browser on a machine with a GPU
(`npx playwright test e2e/perf.spec.ts --headed` with `PERF=1`) and add the numbers here.

## Changes made in this pass

- **Map pages of 5000 points** (the API's maximum) instead of the hook's default 500
  (`pages/DiscoverPage.tsx`). Each page rebuilds the point layer's attributes over all points
  loaded so far, so page-in cost grows with (points ÷ page size) × points. 10k went from 10.7 s to
  2.7 s.
- **Point styles cached** (`components/map/pointStyle.ts`). A point's style depends only on its
  state and genre colour. The accessors now build each distinct style once, and work out a point's
  state once for all four accessors. A full restyle went from 19 ms to 8 ms at 10k points, and
  from 194 ms to 86 ms at 100k (Node, cold accessors).
- **Map list scrolls.** With many points, the map's list alternative grew past the top of the
  screen and rows could not be reached. The controls column can now shrink, so the list scrolls
  inside it (`pages/layout.tsx`, `MapPointList.tsx`).
- **Render-count tests** in `pages/MapLayer.test.tsx`:
  - moving across one point keeps the point layer object and costs at most one commit per move;
  - a refinement settles in at most 12 page commits (measured: 8).

## Beyond fma_small

100k points work, but page-in takes 48 s in mock mode, and part of that is MSW generating and
serializing synthetic pages in a service worker. A catalog that large would want binary or
pre-tiled point data and appending to deck.gl buffers instead of rebuilding them. That is out of
scope for the MVP (fma_small, 8k).
