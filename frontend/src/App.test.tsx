import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ThemeProvider } from "./theme/ThemeProvider";
import { App } from "./App";

describe("App", () => {
  it("renders the Discover screen", () => {
    render(
      <ThemeProvider storageKey={null}>
        <App />
      </ThemeProvider>,
    );
    expect(screen.getByRole("search")).toBeInTheDocument();
  });
});
