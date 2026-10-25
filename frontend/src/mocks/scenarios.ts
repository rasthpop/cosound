// Named mock scenarios. In the browser (`npm run dev:mock`) pick one with `?scenario=<name>`;
// `?mapPoints=10000` swaps the map dataset for synthetic points.
export const SCENARIOS = [
  "happy",
  "degraded-semantic",
  "map-down",
  "no-confident-match",
  "needs-clarification",
  "slow-network",
  "errors",
] as const;

export type Scenario = (typeof SCENARIOS)[number];

export interface ScenarioOptions {
  /** Serve this many synthetic map points instead of the fixture pages. */
  mapPoints?: number;
  /** Artificial latency per response in ms (the `slow-network` scenario uses SLOW_NETWORK_MS). */
  latencyMs?: number;
}

export const SLOW_NETWORK_MS = 1500;
const MAX_SYNTHETIC_POINTS = 200_000;

export function isScenario(value: string | null): value is Scenario {
  return value !== null && (SCENARIOS as readonly string[]).includes(value);
}

/** Scenario and options from a query string such as `?scenario=map-down&mapPoints=10000`. */
export function scenarioFromQuery(search: string): { scenario: Scenario; options: ScenarioOptions } {
  const params = new URLSearchParams(search);
  const name = params.get("scenario");
  const scenario: Scenario = isScenario(name) ? name : "happy";
  const options: ScenarioOptions = {};
  const count = Number(params.get("mapPoints"));
  if (Number.isInteger(count) && count > 0) {
    options.mapPoints = Math.min(count, MAX_SYNTHETIC_POINTS);
  }
  return { scenario, options };
}
