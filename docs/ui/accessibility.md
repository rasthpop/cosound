# Accessibility audit — Discover screen

U05.T01, against ui.md §7 and `ux-states-and-evidence` §6. Audited on 2026-11-02 in mock mode,
Chromium (Playwright).

```bash
cd frontend
npx playwright test e2e/a11y.spec.ts   # this audit (43 tests)
npm run test-storybook                 # every story, axe set to "error"
```

## Result

| Check | How | Result |
|---|---|---|
| axe, serious/critical WCAG 2.1 A/AA | `a11y.spec.ts`: all 10 mock scenarios × desktop (1280×800) and mobile (390×844) × dark and light. Each run checks idle, then after a search; `happy` also checks with the details drawer open | **0 violations** in all 40 runs |
| axe on every view state in isolation | Storybook story tests (`a11y: { test: "error" }`) | 0 violations (74 stories) |
| Keyboard-only path | Scripted walkthrough in `a11y.spec.ts` (below) | passes |
| Live region | Same walkthrough: "3 results for “…”" after a search, "Results refined. …" after feedback | passes |
| Drawer focus loop and return | 25 × Tab and Shift+Tab stay inside the open drawer; Esc closes it and focus returns to the row title it was opened from | passes |
| Focus return from the map | `pages/DetailsLayer.test.tsx`: a canvas pick returns focus to the map region | passes |
| Text contrast on glass over the densest map area | `a11y.spec.ts` (method below) | passes, ≥ 6.3:1 |
| Selection is not shown by color alone | Rows: `aria-current` + accent border + raised background. Map: the selected point is larger and has a wider accent ring than a result (`helpers.test.ts` "selection beats hover beats result, and is more than colour"), plus the pulse ring when motion is allowed | passes |
| Reduced motion stops the pulse | `TrackMap.test.tsx` "is absent without a selection and under reduced motion"; `tokens.test.ts` "reduced motion has no pulse and no transition time"; `TrackMap` story *Reduced motion* | passes |
| Reduced motion stops camera easing | `helpers.test.ts` "flies in 600 ms, and instantly under reduced motion"; the map E2E tests run with `reducedMotion: "reduce"` and click points right after camera moves | passes |

## The keyboard walkthrough (ui.md §7)

Scripted as `keyboard-only walkthrough` in `frontend/e2e/a11y.spec.ts`; only the keyboard is used.

1. On arrival the search input has focus (flow 1). **Esc** leaves the input; **/** brings focus back.
2. Type a query and press **Enter**. The polite live region announces "3 results for “Something chill with a flute”".
3. **Tab** reaches the first result's title. Its feedback actions appear when the row gets keyboard focus (they are hidden by opacity, never removed from the tab order), so **Tab** reaches "Less like this". **Enter** refines the results: the "What changed" strip appears and the live region says "Results refined. …".
4. **Enter** on the result title opens the details drawer and moves focus into it. Tab and Shift+Tab cycle inside the drawer (it is non-modal on desktop so the map stays usable, but Tab loops). **Esc** closes it and focus returns to the title.
5. **Tab** reaches the map controls. **Enter** on "List of map tracks" opens the list alternative. **Tab** to a track and **Enter** selects it: the same action as clicking its point, so the drawer opens.

The canvas itself is a focusable region whose description gives the point and result count and points to the list view. Arrow keys pan, `+`/`−` zoom and `0` resets the view (TrackMap).

## Contrast over the map

axe can't evaluate text over a WebGL canvas (it reports those nodes as "incomplete"), and dense additive dots on the dark theme can glow brighter than any single point color, which the token test (`tokens.test.ts`) assumes as the worst case. So the audit measures the map:

1. Load the map with 10,000 synthetic points (more than the 8,000 of fma_small) and hide the floating UI.
2. Screenshot the canvas and blur it by 12 px, like the panels' `backdrop-filter`.
3. Take the most extreme pixel: the brightest on dark, the darkest on light.
4. Paint the panel's translucent fill over it and compute the WCAG contrast of the text tokens against that.

| Theme | Extreme pixel (blurred) | Body text | Muted text |
|---|---|---|---|
| dark, 10k synthetic | rgb(61, 43, 10) | 15.88 : 1 | 7.52 : 1 |
| light, 10k synthetic | rgb(172, 207, 175) | 18.33 : 1 | 6.31 : 1 |
| dark, real fma_small map (7,993) | rgb(60, 43, 12) | 15.89 : 1 | 7.52 : 1 |
| light, real fma_small map | rgb(200, 212, 227) | 18.62 : 1 | 6.41 : 1 |

All are well above AA (4.5:1). The real projection was measured during U05.T04: the same test runs on a real map with `E2E_REAL_BACKEND=1 API_PROXY_TARGET=… npx playwright test e2e/a11y.spec.ts -g contrast`.

## Findings

None open. Nothing in this audit needed a code change. Earlier in U04, checking the page in a browser had found and fixed layout issues that also affected accessibility: feedback buttons overflowing the drawer, the status pill covering the chips on mobile, and the open drawer covering the search button.
