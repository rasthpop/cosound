// Theme context and hook. The provider (ThemeProvider.tsx) owns the state; views and containers
// read it here. A theme switch only changes `data-theme` on <html>; the CSS variables follow.
import { createContext, useContext } from "react";

import type { MotionSet, SemanticTokens, ThemeName } from "./tokens/types";

/** A chosen theme, or `"system"` to follow `prefers-color-scheme`. */
export type ThemePreference = ThemeName | "system";

export interface ThemeContextValue {
  /** The theme in effect. */
  theme: ThemeName;
  /** What the user chose; `"system"` until they choose. */
  preference: ThemePreference;
  setPreference(preference: ThemePreference): void;
  /** True under `prefers-reduced-motion: reduce`. */
  reducedMotion: boolean;
  /** The motion set to use: `motion.reduced` when `reducedMotion`. */
  motion: MotionSet;
  /** The active theme's semantic tokens, for code that cannot read CSS variables (deck.gl). */
  tokens: SemanticTokens;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (value === null) {
    throw new Error("useTheme must be used inside <ThemeProvider>.");
  }
  return value;
}
