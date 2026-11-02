import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App, HARNESS_PATH } from "./App";
import { ThemeProvider } from "./theme/ThemeProvider";

const renderApp = () =>
  render(
    <ThemeProvider storageKey={null}>
      <App />
    </ThemeProvider>,
  );

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/");
});

describe("App", () => {
  it("renders the Discover screen, with no router", () => {
    renderApp();
    expect(screen.getByRole("search")).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "Discover music" })).toBeInTheDocument();
  });

  it("serves the contract harness at its dev-only path in development", async () => {
    window.history.replaceState(null, "", HARNESS_PATH);
    renderApp();
    expect(await screen.findByRole("heading", { name: /contract harness/i })).toBeInTheDocument();
    expect(screen.queryByRole("main", { name: "Discover music" })).toBeNull();
  });
});
