// MSW in the browser for `npm run dev:mock` (VITE_API_MODE=mock). The scenario comes from the
// page URL: `?scenario=map-down`, `?mapPoints=10000`.
import { setupWorker } from "msw/browser";

import { handlersFor } from "./handlers";
import { scenarioFromQuery } from "./scenarios";

export async function startMockWorker(): Promise<void> {
  const { scenario, options } = scenarioFromQuery(window.location.search);
  const worker = setupWorker(...handlersFor(scenario, options));
  await worker.start({ onUnhandledRequest: "bypass", quiet: false });
  console.info(`[mocks] API mocked with scenario "${scenario}"`, options);
}
