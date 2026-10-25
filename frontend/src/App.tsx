import { lazy, Suspense } from "react";

// Composition root. The interface itself is defined by the separate UI/UX plan (skills/phases/ui/).
// The dev-only contract harness (P09.T09) is compiled out of production builds.
const ContractHarness = import.meta.env.DEV
  ? lazy(() => import("./dev/ContractHarness").then((m) => ({ default: m.ContractHarness })))
  : null;

export const HARNESS_PATH = "/__dev/harness";

export function App() {
  if (ContractHarness && window.location.pathname === HARNESS_PATH) {
    return (
      <Suspense fallback={<p>loading harness…</p>}>
        <ContractHarness />
      </Suspense>
    );
  }
  return <p>Semantic Music Discovery: interface not implemented yet.</p>;
}
