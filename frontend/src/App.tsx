import { lazy, Suspense } from "react";

import { DiscoverPage } from "./pages/DiscoverPage";

// Composition root: the Discover screen is the whole interface (ui.md §3), with no router.
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
  return <DiscoverPage />;
}
