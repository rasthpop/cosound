// Primitive tokens: raw values from the UI/UX plan (skills/phases/ui/ui.md §2).
// Nothing outside theme/ reads these. Semantic themes (semantic.ts) map meanings onto them,
// so changing the look means changing values here or the mapping there, never a component.

/** Neutral "ink" scale, from the near-black canvas up to white. */
export const ink = {
  950: "#0B0B0F", // canvas (ui.md §2)
  900: "#121218", // glass panel base colour
  850: "#18181F",
  800: "#1F1F28",
  700: "#2A2A35",
  600: "#3A3A47",
  500: "#5A5A6A",
  450: "#737383", // weak match band on light surfaces
  400: "#8A8A9A",
  300: "#A9A9B8",
  200: "#C9C9D4",
  100: "#E6E6EC",
  50: "#F4F4F7",
  0: "#FFFFFF",
} as const;

/** The one accent (ui.md §2): focus, selection and the primary action only. */
export const violet = {
  200: "#DDD6FE",
  300: "#C4B5FD",
  400: "#A78BFA", // default accent
  500: "#8B5CF6",
  600: "#7C3AED",
  700: "#6D28D9",
} as const;

/** Warm end of the ink-to-vermilion ramp (visual reference: Subwave). Match strength only. */
export const vermilion = {
  200: "#FFC2B3",
  300: "#FF9B85",
  400: "#FF7556",
  500: "#F2502E",
  600: "#D13B1C",
  700: "#A82D14",
  800: "#7F1D0E",
} as const;

/** Evidence identity (audio + metadata); not a status colour. */
export const teal = {
  300: "#5EEAD4",
  400: "#2DD4BF",
  600: "#0D9488",
  700: "#0F766E",
} as const;

/** Status hues, reserved for system state and feedback; always shown with an icon and a label. */
export const green = { 400: "#4ADE80", 700: "#15803D" } as const;
export const amber = { 300: "#FCD34D", 400: "#FBBF24", 700: "#B45309" } as const;
export const red = { 400: "#F87171", 700: "#B91C1C" } as const;

/**
 * Categorical genre hues: the dataviz skill's validated reference palette (same hues and slot
 * order), each mode stepped for its own surface. Validation results: theme/scales/categorical.test.ts.
 */
export const categorical = {
  dark: ["#3987E5", "#D95926", "#199E70", "#C98500", "#D55181", "#008300", "#9085E9", "#E66767"],
  light: ["#2A78D6", "#EB6834", "#1BAF7A", "#EDA100", "#E87BA4", "#008300", "#6250D6", "#E34948"],
} as const;

/** Translucent layers. The panel value is the plan's glass surface. */
export const alpha = {
  glassDark: "rgba(18, 18, 24, 0.72)", // ui.md §2 floating panel
  raisedDark: "rgba(31, 31, 40, 0.88)",
  hairlineDark: "rgba(255, 255, 255, 0.08)",
  strongLineDark: "rgba(255, 255, 255, 0.16)",
  glassLight: "rgba(255, 255, 255, 0.86)",
  raisedLight: "rgba(255, 255, 255, 0.94)",
  hairlineLight: "rgba(11, 11, 15, 0.10)",
  strongLineLight: "rgba(11, 11, 15, 0.20)",
} as const;

export const font = {
  family: {
    sans: "'Inter Variable', Inter, ui-sans-serif, system-ui, sans-serif",
  },
  /** px: metadata 13, body/track title 15, heading 20, display 28 (ui.md §2). */
  size: { 13: 13, 15: 15, 20: 20, 28: 28 },
  lineHeight: { 13: 18, 15: 22, 20: 28, 28: 36 },
  weight: { regular: 400, medium: 500 },
} as const;

/** 8 px grid; a half step for tight insets. Values in px. */
export const space = {
  0: 0,
  0.5: 4,
  1: 8,
  1.5: 12,
  2: 16,
  3: 24,
  4: 32,
  6: 48,
  8: 64,
} as const;

/** Corner radii in px (panels 12-16 px). */
export const radius = { sm: 8, md: 12, lg: 16, pill: 9999 } as const;

/** Backdrop blur in px for glass panels. */
export const blur = { panel: 12 } as const;

/** ms. Panels 150-250, camera fly-to 600 (ui.md §2); the selection pulse is slow. */
export const duration = { 0: 0, 150: 150, 250: 250, 600: 600, 1600: 1600 } as const;

export const easing = {
  out: "cubic-bezier(0.2, 0, 0, 1)",
  linear: "linear",
} as const;

/** Map point geometry in px and opacities (ui.md §2: 2-4 px dots at ~0.55, results 6-8 px). */
export const point = {
  radius: { dot: 1.5, hover: 2.5, result: 3.5, selected: 4 },
  ring: { thin: 1, selected: 2 },
  opacity: { dot: 0.55, dimmed: 0.15, full: 1 },
} as const;

/** px; results rows ~56 px (ui.md §2), with a denser alternative. */
export const rowHeight = { comfortable: 56, compact: 44 } as const;
