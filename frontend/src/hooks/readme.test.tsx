// The README is the UI track's contract: every field a hook returns must be documented there.
import { readFileSync } from "node:fs";

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import * as hooks from "./index";

const client = createApiClient({ baseUrl: "http://api.test" });
// vitest runs from frontend/ (import.meta.url is not a file URL under jsdom)
const readme = readFileSync("src/hooks/README.md", "utf8");

/** The README section of one hook (from its `## \`name` heading to the next heading). */
function section(name: string): string {
  const start = readme.indexOf(`## \`${name}(`);
  expect(start, `README section for ${name}`).toBeGreaterThan(-1);
  const end = readme.indexOf("\n## ", start + 1);
  return readme.slice(start, end === -1 ? undefined : end);
}

const rendered: Record<string, () => object> = {
  useMusicSearch: () => renderHook(() => hooks.useMusicSearch({ client })).result.current,
  useTrackFeedback: () =>
    renderHook(() =>
      hooks.useTrackFeedback({ sessionId: null, queryId: null, applyRefreshed: () => undefined }, { client }),
    ).result.current,
  useTrackDetails: () => renderHook(() => hooks.useTrackDetails(null, { client })).result.current,
  useMusicMap: () => renderHook(() => hooks.useMusicMap({ client, enabled: false })).result.current,
  useSystemStatus: () => renderHook(() => hooks.useSystemStatus({ client })).result.current,
};
// hooks that return a single value, not an object of fields: their section must exist
const scalar = ["useMediaUrl"];

describe("hooks README", () => {
  it.each(Object.keys(rendered))("documents every field %s returns", (name) => {
    const text = section(name);
    for (const field of Object.keys(rendered[name]!())) {
      expect(text, `${name}.${field}`).toContain(`\`${field}\``);
    }
  });

  it("covers exactly the hooks exported from index.ts", () => {
    const exported = Object.keys(hooks).filter((k) => k.startsWith("use"));
    expect(exported.sort()).toEqual([...Object.keys(rendered), ...scalar].sort());
  });

  it.each(scalar)("documents %s", (name) => {
    expect(section(name)).toContain("→");
  });
});
