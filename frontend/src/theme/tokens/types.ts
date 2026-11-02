// The semantic token contract. Every theme `satisfies SemanticTokens`, so a theme that forgets
// a token does not compile. Names say what a value means in this product, not what it looks
// like; components and the CSS emitter (U01.T02) consume only these.

/** A CSS colour: `#rrggbb` or `rgba(r, g, b, a)`. */
export type Color = string;
/** CSS pixels. */
export type Px = number;
/** Milliseconds. */
export type Ms = number;

export type ThemeName = "dark" | "light";

/** Eight categorical hues in their fixed, validated slot order. */
export type CategoricalPalette = readonly [Color, Color, Color, Color, Color, Color, Color, Color];

export interface MotionSet {
  duration: { fast: Ms; base: Ms; camera: Ms; pulse: Ms };
  easing: { out: string; linear: string };
  /** False when the selected-point pulse must not run. */
  pulse: boolean;
}

export interface DensitySet {
  rowHeight: Px;
  rowGap: Px;
  panelPadding: Px;
}

export interface SemanticTokens {
  color: {
    surface: {
      /** The page and map background. */
      canvas: Color;
      /** Floating glass panels over the map (used with `blur.panel`). */
      panel: Color;
      /** Menus, popovers and the hovered row, above a panel. */
      raised: Color;
    };
    text: {
      default: Color;
      muted: Color;
      /** Text on `accent.default` (the primary action). */
      onAccent: Color;
    };
    border: { hairline: Color; strong: Color };
    focus: { ring: Color };
    /** Focus, selection and the primary action only. */
    accent: { default: Color; hover: Color; subtle: Color };
    /** System states; always paired with an icon and a label. */
    state: {
      loading: Color;
      empty: Color;
      error: Color;
      warning: Color;
      degraded: Color;
    };
    /** Evidence-status badges (`TrackResult.audio_available`, evidence status). */
    evidence: { audioAndMetadata: Color; metadataOnly: Color; noAudio: Color };
    /** Match-strength bands; a sequential ramp, never shown as a probability. */
    match: { strong: Color; partial: Color; weak: Color };
    feedback: { positive: Color; negative: Color; neutral: Color };
    map: {
      /** Behind the points; the darkest (dark theme) or lightest (light theme) map pixel. */
      backdrop: Color;
      point: {
        /** Fill of a point without a genre (`MapPoint.genre === null`). */
        default: Color;
        /** Ring of the hovered point. */
        hover: Color;
        /** Ring of the selected point. */
        selected: Color;
        /** Fill tint of points dimmed while results are highlighted. */
        dimmed: Color;
        /** Thin ring around search results. */
        result: Color;
        /** Fill of a point whose genre is outside the palette (folded into "Other"). */
        other: Color;
      };
      /** Genre hues for the map (`theme/scales/categorical`). */
      categorical: CategoricalPalette;
    };
  };
  opacity: { point: { default: number; dimmed: number; result: number } };
  size: {
    point: { default: Px; hover: Px; result: Px; selected: Px };
    ring: { result: Px; selected: Px; focus: Px };
    icon: Px;
    /** lucide stroke width at `icon` size (ui.md §2: 16 px / 1.5). */
    iconStroke: Px;
    hitTarget: Px;
  };
  blur: { panel: Px };
  radius: { sm: Px; md: Px; lg: Px; pill: Px };
  font: {
    family: { sans: string };
    size: { meta: Px; body: Px; heading: Px; display: Px };
    lineHeight: { meta: Px; body: Px; heading: Px; display: Px };
    weight: { regular: number; medium: number };
  };
  space: { xs: Px; sm: Px; md: Px; lg: Px; xl: Px; xxl: Px; xxxl: Px };
  density: { comfortable: DensitySet; compact: DensitySet };
  motion: {
    default: MotionSet;
    /** Used under `prefers-reduced-motion`: no pulse, instant transitions. */
    reduced: MotionSet;
  };
}
