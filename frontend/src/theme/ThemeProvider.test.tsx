import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { THEME_STORAGE_KEY, ThemeProvider, type ThemeProviderProps } from "./ThemeProvider";
import { dark, light } from "./tokens/semantic";
import { useTheme, type ThemeContextValue } from "./useTheme";

// --- a controllable matchMedia ----------------------------------------------------------------

type Listener = () => void;
const active = new Set<string>();
const listeners = new Map<string, Set<Listener>>();

function setMedia(query: string, on: boolean) {
  if (on) active.add(query);
  else active.delete(query);
  act(() => listeners.get(query)?.forEach((l) => l()));
}

function installMatchMedia() {
  window.matchMedia = ((query: string) => ({
    media: query,
    get matches() {
      return active.has(query);
    },
    addEventListener: (_: string, l: Listener) => {
      if (!listeners.has(query)) listeners.set(query, new Set());
      listeners.get(query)?.add(l);
    },
    removeEventListener: (_: string, l: Listener) => listeners.get(query)?.delete(l),
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

// The real generated variables (vitest stubs CSS imports, so read the file).
// jsdom gives modules an http: import.meta.url, so resolve from the vitest root (frontend/).
const tokensCss = readFileSync(resolve("src/theme/generated/tokens.css"), "utf8");

/** An in-memory Storage: Node's experimental global localStorage shadows jsdom's in tests. */
function installStorage(): Storage {
  const data = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (k) => data.get(k) ?? null,
    key: (i) => [...data.keys()][i] ?? null,
    removeItem: (k) => void data.delete(k),
    setItem: (k, v) => void data.set(k, String(v)),
  };
  Object.defineProperty(window, "localStorage", { value: storage, configurable: true });
  return storage;
}

// --- helpers -----------------------------------------------------------------------------------

let current: ThemeContextValue | null = null;
const capture = (value: ThemeContextValue) => {
  current = value;
};

function Probe({ onValue }: { onValue: (value: ThemeContextValue) => void }) {
  const value = useTheme();
  onValue(value);
  return <span data-testid="theme">{value.theme}</span>;
}

function renderTheme(props: Omit<ThemeProviderProps, "children"> = {}) {
  return render(
    <ThemeProvider storageKey={null} {...props}>
      <Probe onValue={capture} />
    </ThemeProvider>,
  );
}

const html = () => document.documentElement;
const cssVar = (name: string) => getComputedStyle(html()).getPropertyValue(name).trim();
const attributes = () =>
  Object.fromEntries([...html().attributes].map((a) => [a.name, a.value]).filter(([n]) => n !== "data-theme"));

let style: HTMLStyleElement;
let storage: Storage;
beforeEach(() => {
  installMatchMedia();
  storage = installStorage();
  style = document.createElement("style");
  style.textContent = tokensCss; // the real generated variables; jsdom ignores @theme
  document.head.append(style);
});
afterEach(() => {
  cleanup();
  style.remove();
  html().removeAttribute("data-theme");
  active.clear();
  listeners.clear();
  current = null;
});

describe("ThemeProvider", () => {
  it("defaults to dark and applies its variables", () => {
    renderTheme();
    expect(html().getAttribute("data-theme")).toBe("dark");
    expect(cssVar("--token-color-surface-canvas")).toBe(dark.color.surface.canvas);
    expect(current?.tokens).toBe(dark);
  });

  it("switching theme changes only data-theme and the computed variables", () => {
    renderTheme();
    const before = { attrs: attributes(), bodyStyle: document.body.getAttribute("style") };
    act(() => current?.setPreference("light"));
    expect(html().getAttribute("data-theme")).toBe("light");
    expect(attributes()).toEqual(before.attrs);
    expect(document.body.getAttribute("style")).toBe(before.bodyStyle);
    expect(cssVar("--token-color-surface-canvas")).toBe(light.color.surface.canvas);
    expect(cssVar("--token-color-text-default")).toBe(light.color.text.default);
    expect(screen.getByTestId("theme")).toHaveTextContent("light");
  });

  it("follows prefers-color-scheme only while no theme was chosen", () => {
    active.add("(prefers-color-scheme: light)");
    renderTheme();
    expect(current?.theme).toBe("light");
    setMedia("(prefers-color-scheme: light)", false);
    expect(current?.theme).toBe("dark");
    act(() => current?.setPreference("light"));
    setMedia("(prefers-color-scheme: dark)", true);
    expect(current?.theme).toBe("light"); // an explicit choice wins over the system
    act(() => current?.setPreference("system"));
    expect(current?.theme).toBe("dark");
  });

  it("remembers the choice and tolerates blocked storage", () => {
    const { unmount } = renderTheme({ storageKey: THEME_STORAGE_KEY });
    act(() => current?.setPreference("light"));
    expect(storage.getItem(THEME_STORAGE_KEY)).toBe("light");
    unmount();
    renderTheme({ storageKey: THEME_STORAGE_KEY });
    expect(current?.preference).toBe("light");

    const blocked = vi.spyOn(storage, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    renderTheme({ storageKey: THEME_STORAGE_KEY });
    expect(current?.preference).toBe("system");
    blocked.mockRestore();
  });

  it("exposes reduced motion from prefers-reduced-motion", () => {
    renderTheme();
    expect(current?.reducedMotion).toBe(false);
    expect(current?.motion.pulse).toBe(true);
    setMedia("(prefers-reduced-motion: reduce)", true);
    expect(current?.reducedMotion).toBe(true);
    expect(current?.motion).toBe(dark.motion.reduced);
    expect(current?.motion.pulse).toBe(false);
  });

  it("tokens.css zeroes the motion variables under prefers-reduced-motion", () => {
    const media = /@media \(prefers-reduced-motion: reduce\) \{([\s\S]*?)\n\}/.exec(tokensCss);
    expect(media?.[1]).toContain("--token-motion-duration-fast: 0ms;");
    expect(media?.[1]).toContain("--token-motion-duration-camera: 0ms;");
    // the override must come after the default motion block (same :root specificity)
    expect(tokensCss.indexOf("--token-motion-duration-fast: 150ms;")).toBeLessThan(media?.index ?? -1);
    // and themes must not redefine motion with a more specific selector
    const themeBlocks = tokensCss.split("@media")[0]?.split(/\n(?=:root)/).filter((b) => b.includes("data-theme"));
    expect(themeBlocks?.every((b) => !b.includes("--token-motion"))).toBe(true);
  });

  it("useTheme outside a provider fails loudly", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe onValue={capture} />)).toThrow(/ThemeProvider/);
    spy.mockRestore();
  });
});
