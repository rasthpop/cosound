// Semantic themes: product meanings mapped onto primitives. Dark is the default (ui.md §2);
// light is optional and changes values only. A theme switch never requires a component change.
import {
  alpha,
  amber,
  blur,
  categorical,
  duration,
  easing,
  font,
  green,
  ink,
  point,
  radius,
  red,
  rowHeight,
  space,
  teal,
  vermilion,
  violet,
} from "./primitives";
import type { MotionSet, SemanticTokens, ThemeName } from "./types";

const motion: MotionSet = {
  duration: { fast: duration[150], base: duration[250], camera: duration[600], pulse: duration[1600] },
  easing: { out: easing.out, linear: easing.linear },
  pulse: true,
};

const reducedMotion: MotionSet = {
  duration: { fast: duration[0], base: duration[0], camera: duration[0], pulse: duration[0] },
  easing: { out: easing.linear, linear: easing.linear },
  pulse: false,
};

/** Everything that is not colour is shared by both themes. */
const shared = {
  opacity: {
    point: { default: point.opacity.dot, dimmed: point.opacity.dimmed, result: point.opacity.full },
  },
  size: {
    point: {
      default: point.radius.dot,
      hover: point.radius.hover,
      result: point.radius.result,
      selected: point.radius.selected,
    },
    ring: { result: point.ring.thin, selected: point.ring.selected, focus: 2 },
    icon: 16,
    iconStroke: 1.5,
    hitTarget: 24,
  },
  blur: { panel: blur.panel },
  radius: { sm: radius.sm, md: radius.md, lg: radius.lg, pill: radius.pill },
  font: {
    family: { sans: font.family.sans },
    size: { meta: font.size[13], body: font.size[15], heading: font.size[20], display: font.size[28] },
    lineHeight: {
      meta: font.lineHeight[13],
      body: font.lineHeight[15],
      heading: font.lineHeight[20],
      display: font.lineHeight[28],
    },
    weight: { regular: font.weight.regular, medium: font.weight.medium },
  },
  space: {
    xs: space[0.5],
    sm: space[1],
    md: space[1.5],
    lg: space[2],
    xl: space[3],
    xxl: space[4],
    xxxl: space[6],
  },
  density: {
    comfortable: { rowHeight: rowHeight.comfortable, rowGap: space[0.5], panelPadding: space[2] },
    compact: { rowHeight: rowHeight.compact, rowGap: space[0], panelPadding: space[1.5] },
  },
  motion: { default: motion, reduced: reducedMotion },
} satisfies Omit<SemanticTokens, "color">;

export const dark = {
  ...shared,
  color: {
    surface: { canvas: ink[950], panel: alpha.glassDark, raised: alpha.raisedDark },
    text: { default: ink[50], muted: ink[300], onAccent: ink[950] },
    border: { hairline: alpha.hairlineDark, strong: alpha.strongLineDark },
    focus: { ring: violet[400] },
    accent: { default: violet[400], hover: violet[300], subtle: violet[700] },
    state: {
      loading: ink[400],
      empty: ink[400],
      error: red[400],
      warning: amber[400],
      degraded: amber[300],
    },
    evidence: { audioAndMetadata: teal[300], metadataOnly: ink[300], noAudio: ink[400] },
    // ink -> vermilion, ordered by contrast with the canvas: weak is closest, strong stands out most
    match: { strong: vermilion[300], partial: vermilion[400], weak: ink[400] },
    feedback: { positive: green[400], negative: red[400], neutral: ink[300] },
    map: {
      backdrop: ink[950],
      point: {
        default: ink[400],
        hover: ink[100],
        selected: violet[400],
        dimmed: ink[500],
        result: ink[50],
        other: ink[300],
      },
      categorical: categorical.dark,
    },
  },
} satisfies SemanticTokens;

export const light = {
  ...shared,
  color: {
    surface: { canvas: ink[50], panel: alpha.glassLight, raised: alpha.raisedLight },
    text: { default: ink[950], muted: ink[500], onAccent: ink[0] },
    border: { hairline: alpha.hairlineLight, strong: alpha.strongLineLight },
    focus: { ring: violet[600] },
    accent: { default: violet[600], hover: violet[700], subtle: violet[200] },
    state: {
      loading: ink[500],
      empty: ink[500],
      error: red[700],
      warning: amber[700],
      degraded: amber[700],
    },
    evidence: { audioAndMetadata: teal[700], metadataOnly: ink[600], noAudio: ink[500] },
    match: { strong: vermilion[800], partial: vermilion[700], weak: ink[450] },
    feedback: { positive: green[700], negative: red[700], neutral: ink[500] },
    map: {
      backdrop: ink[50],
      point: {
        default: ink[500],
        hover: ink[800],
        selected: violet[600],
        dimmed: ink[300],
        result: ink[950],
        other: ink[700],
      },
      categorical: categorical.light,
    },
  },
} satisfies SemanticTokens;

export const themes: Record<ThemeName, SemanticTokens> = { dark, light };

/** lucide props for every icon (theme-independent): `<Play {...ICON} />`. */
export const ICON = { size: shared.size.icon, strokeWidth: shared.size.iconStroke } as const;
export const DEFAULT_THEME: ThemeName = "dark";
