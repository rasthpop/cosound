import { describe, expect, it } from "vitest";

import { cn } from "./cn";

describe("cn", () => {
  it("keeps a token font size and a token text colour together", () => {
    expect(cn("text-body", "text-muted")).toBe("text-body text-muted");
  });

  it("lets later token utilities override earlier ones of the same kind", () => {
    expect(cn("text-body", "text-meta")).toBe("text-meta");
    expect(cn("text-fg", "text-muted")).toBe("text-muted");
    expect(cn("bg-surface-panel", "bg-surface-raised")).toBe("bg-surface-raised");
    expect(cn("rounded-lg", "rounded-pill")).toBe("rounded-pill");
    expect(cn("font-regular", "font-medium")).toBe("font-medium");
    expect(cn("p-2", "p-1")).toBe("p-1");
  });

  it("handles conditional classes", () => {
    const hidden = false;
    expect(cn("text-fg", hidden && "hidden", undefined, ["border-hairline"])).toBe("text-fg border-hairline");
  });
});
