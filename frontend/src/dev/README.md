# dev/: development-only pages

`ContractHarness.tsx` (P09.T09) is a deliberately plain, unstyled page at `/__dev/harness`. It
drives the four hooks end to end: search, the plate as raw fields, every feedback type, track
details with neighbors, and map points with pagination and filters. It shows that a visual
layer needs nothing but the hooks. It is **not** the interface and makes no design decisions.
The real interface is the Discover screen (`src/pages/DiscoverPage.tsx`) at `/`. The harness is
kept, dev-only, as a hook-level check that needs no visual layer (the U05 isolation test leans on it).

- It is served only by the dev server (`import.meta.env.DEV`) and compiled out of production
  builds. `npm run build` ends with `scripts/check-bundle.mjs`, which fails if the bundle contains
  the harness, MSW or `mockServiceWorker.js` (the worker is dropped from non-mock builds by a
  small plugin in `vite.config.ts`).
- The interface on mocks: `npm run dev:mock`, then `http://localhost:5173/?scenario=happy`.
- With mocks: `npm run dev:mock`, then open `http://localhost:5173/__dev/harness?scenario=happy`
  (or any other scenario from `src/mocks/scenarios.ts`).
- Against the real backend: `make serve` in the repo root, then
  `API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev` and open `/__dev/harness`.
- End-to-end tests: `npm run e2e` (mock mode).
  `E2E_REAL_BACKEND=1 API_PROXY_TARGET=http://127.0.0.1:8000 npm run e2e` also runs the
  real-backend smoke test.
