// @vitest-environment node
// Compiles the real global.css with Tailwind to prove that only token-backed utilities exist.
import { readFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { compile } from "@tailwindcss/node";
import { beforeAll, describe, expect, it } from "vitest";

const globalCss = fileURLToPath(new URL("./global.css", import.meta.url));

let build: (candidates: string[]) => string;
beforeAll(async () => {
  const compiler = await compile(await readFile(globalCss, "utf8"), {
    base: dirname(globalCss),
    onDependency: () => {},
  });
  build = (candidates) => compiler.build(candidates);
});

/** The CSS rule for one utility class, or undefined when Tailwind generated none. */
function rule(css: string, className: string): string | undefined {
  const escaped = className.replace(/[.:/[\]]/g, (c) => `\\\\${c}`);
  return new RegExp(`\\.${escaped}\\s*\\{[^}]*\\}`).exec(css)?.[0];
}

describe("Tailwind theme", () => {
  it("has no default palette or scales", () => {
    const css = build(["bg-red-500", "text-xl", "shadow-md", "rounded-xl", "font-bold", "ease-in-out", "blur-sm"]);
    for (const cls of ["bg-red-500", "text-xl", "shadow-md", "rounded-xl", "font-bold", "ease-in-out", "blur-sm"]) {
      expect(rule(css, cls), cls).toBeUndefined();
    }
  });

  it("maps semantic utilities to token variables", () => {
    const css = build([
      "bg-surface-panel",
      "text-muted",
      "border-hairline",
      "bg-match-strong",
      "text-body",
      "font-medium",
      "rounded-lg",
      "backdrop-blur-panel",
      "p-2",
    ]);
    expect(rule(css, "bg-surface-panel")).toContain("var(--token-color-surface-panel)");
    expect(rule(css, "text-muted")).toContain("var(--token-color-text-muted)");
    expect(rule(css, "border-hairline")).toContain("var(--token-color-border-hairline)");
    expect(rule(css, "bg-match-strong")).toContain("var(--token-color-match-strong)");
    expect(rule(css, "text-body")).toContain("var(--token-font-size-body)");
    expect(rule(css, "font-medium")).toContain("var(--token-font-weight-medium)");
    expect(rule(css, "rounded-lg")).toContain("var(--token-radius-lg)");
    expect(rule(css, "backdrop-blur-panel")).toContain("var(--token-blur-panel)");
    // spacing is the 8 px token grid (inlined: p-2 = 2 × space.sm)
    expect(rule(css, "p-2")).toContain("calc(var(--token-space-sm) * 2)");
  });

  it("does not emit Tailwind's default colour variables", () => {
    const css = build(["bg-surface-canvas"]);
    expect(css).not.toMatch(/--color-red-500/);
    expect(css).not.toMatch(/oklch\(/);
  });
});
