// Owns the theme choice and the user's motion preference.
// - The theme is applied by setting `data-theme` on <html>; tokens.css does the rest.
// - With no explicit choice the theme follows `prefers-color-scheme` (dark when there is none).
// - `reducedMotion` mirrors `prefers-reduced-motion`; tokens.css applies it to the CSS motion
//   variables on its own, and JS animation (pulse, camera) reads `motion` from the context.
import { useCallback, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";

import { DEFAULT_THEME, themes } from "./tokens/semantic";
import type { ThemeName } from "./tokens/types";
import { ThemeContext, type ThemeContextValue, type ThemePreference } from "./useTheme";

export const THEME_STORAGE_KEY = "music-discovery.theme";
const LIGHT_QUERY = "(prefers-color-scheme: light)";
const DARK_QUERY = "(prefers-color-scheme: dark)";
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function matches(query: string): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(query).matches
    : false;
}

function subscribe(query: string) {
  return (onChange: () => void) => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
    const list = window.matchMedia(query);
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  };
}

function useMediaQuery(query: string): boolean {
  const sub = useMemo(() => subscribe(query), [query]);
  return useSyncExternalStore(sub, () => matches(query), () => false);
}

function isPreference(value: string | null): value is ThemePreference {
  return value === "system" || (value !== null && value in themes);
}

function readStored(key: string): ThemePreference | null {
  try {
    const value = window.localStorage.getItem(key);
    return isPreference(value) ? value : null;
  } catch {
    return null; // storage blocked (private mode, sandbox): fall back to the system preference
  }
}

function writeStored(key: string, value: ThemePreference): void {
  try {
    if (value === "system") window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // not persisted; the choice still applies for this page
  }
}

export interface ThemeProviderProps {
  children: ReactNode;
  /** Initial preference when nothing is stored; `"system"` by default. */
  defaultPreference?: ThemePreference;
  /** localStorage key for the user's choice; `null` disables persistence (tests, stories). */
  storageKey?: string | null;
  /** Force reduced motion on or off (stories, tests); by default it follows the media query. */
  reducedMotion?: boolean;
}

export function ThemeProvider({
  children,
  defaultPreference = "system",
  storageKey = THEME_STORAGE_KEY,
  reducedMotion: reducedOverride,
}: ThemeProviderProps) {
  const [preference, setPreferenceState] = useState<ThemePreference>(
    () => (storageKey ? readStored(storageKey) : null) ?? defaultPreference,
  );
  const prefersLight = useMediaQuery(LIGHT_QUERY);
  const prefersDark = useMediaQuery(DARK_QUERY);
  const prefersReduced = useMediaQuery(REDUCED_MOTION_QUERY);
  const reducedMotion = reducedOverride ?? prefersReduced;

  const systemTheme: ThemeName = prefersLight && !prefersDark ? "light" : DEFAULT_THEME;
  const theme: ThemeName = preference === "system" ? systemTheme : preference;

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const setPreference = useCallback(
    (next: ThemePreference) => {
      setPreferenceState(next);
      if (storageKey) writeStored(storageKey, next);
    },
    [storageKey],
  );

  const value = useMemo<ThemeContextValue>(() => {
    const tokens = themes[theme];
    return {
      theme,
      preference,
      setPreference,
      reducedMotion,
      motion: reducedMotion ? tokens.motion.reduced : tokens.motion.default,
      tokens,
    };
  }, [theme, preference, setPreference, reducedMotion]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
