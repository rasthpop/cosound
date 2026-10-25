import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";

async function enableMocks(): Promise<void> {
  if (import.meta.env.VITE_API_MODE !== "mock") return;
  const { startMockWorker } = await import("./mocks/browser");
  await startMockWorker();
}

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element in index.html");
}

void enableMocks().then(() => {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
