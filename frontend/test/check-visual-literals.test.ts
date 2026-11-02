// @vitest-environment node
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

const script = resolve("scripts/check-visual-literals.mjs");
const dirs: string[] = [];

function check(files: Record<string, string>) {
  const dir = mkdtempSync(join(tmpdir(), "literals-"));
  dirs.push(dir);
  for (const [name, text] of Object.entries(files)) writeFileSync(join(dir, name), text);
  const run = spawnSync(process.execPath, [script, dir], { encoding: "utf8" });
  return { status: run.status, output: run.stderr + run.stdout };
}

afterEach(() => {
  for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true });
});

describe("check-visual-literals", () => {
  it("fails on a planted bg-[#fff]", () => {
    const { status, output } = check({ "Planted.tsx": 'export const X = () => <div className="bg-[#fff] p-2" />;\n' });
    expect(status).toBe(1);
    expect(output).toContain("Planted.tsx:1");
    expect(output).toContain("bg-[#fff]");
  });

  it.each([
    ['style={{ color: "#a78bfa" }}', "hex colour"],
    ['style={{ background: "rgba(0, 0, 0, 0.5)" }}', "colour function"],
    ["color: hsl(0 0% 100%);", "colour function"],
    ['className="p-[13px]"', "Tailwind arbitrary value"],
    ['className="text-[var(--x)]"', "Tailwind arbitrary value"],
    ['className="[color:red]"', "Tailwind arbitrary property"],
  ])("flags %s", (snippet, rule) => {
    const { status, output } = check({ "View.tsx": `${snippet}\n` });
    expect(status).toBe(1);
    expect(output).toContain(rule);
  });

  it("passes token utilities, data attributes and ordinary code", () => {
    const { status, output } = check({
      "Ok.tsx": [
        'const cls = "bg-surface-panel text-muted rounded-lg p-2 backdrop-blur-panel";',
        "const pick = items[0]; const id = `#${anchor}`;",
        'export const V = () => <a href="#results" data-state="open" className={cls} />;',
      ].join("\n"),
    });
    expect(output).not.toMatch(/literal visual value/);
    expect(status).toBe(0);
  });
});
