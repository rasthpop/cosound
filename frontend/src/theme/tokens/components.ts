// Component tokens: per-component choices, derived from a theme's semantic tokens only.
// Views read these (through the CSS variables emitted in U01.T02) or semantic tokens, never
// primitives.
import type { Color, Px, SemanticTokens } from "./types";

export interface ComponentTokens {
  panel: { background: Color; border: Color; radius: Px; blur: Px; padding: Px };
  trackRow: {
    height: Px;
    gap: Px;
    hoverBackground: Color;
    selectedBorder: Color;
    titleSize: Px;
    titleWeight: number;
    metaSize: Px;
    metaColor: Color;
  };
  chip: { radius: Px; border: Color; text: Color; size: Px };
  button: { radius: Px; primaryBackground: Color; primaryHover: Color; primaryText: Color };
  mapPoint: {
    radius: Px;
    resultRadius: Px;
    selectedRadius: Px;
    resultRing: Px;
    selectedRing: Px;
  };
}

export function componentTokens(t: SemanticTokens): ComponentTokens {
  return {
    panel: {
      background: t.color.surface.panel,
      border: t.color.border.hairline,
      radius: t.radius.lg,
      blur: t.blur.panel,
      padding: t.density.comfortable.panelPadding,
    },
    trackRow: {
      height: t.density.comfortable.rowHeight,
      gap: t.density.comfortable.rowGap,
      hoverBackground: t.color.surface.raised,
      selectedBorder: t.color.accent.default,
      // track titles 15/500, metadata 13/400 in a muted token (ui.md §2)
      titleSize: t.font.size.body,
      titleWeight: t.font.weight.medium,
      metaSize: t.font.size.meta,
      metaColor: t.color.text.muted,
    },
    chip: {
      radius: t.radius.pill,
      border: t.color.border.strong,
      text: t.color.text.default,
      size: t.font.size.meta,
    },
    button: {
      radius: t.radius.md,
      primaryBackground: t.color.accent.default,
      primaryHover: t.color.accent.hover,
      primaryText: t.color.text.onAccent,
    },
    mapPoint: {
      radius: t.size.point.default,
      resultRadius: t.size.point.result,
      selectedRadius: t.size.point.selected,
      resultRing: t.size.ring.result,
      selectedRing: t.size.ring.selected,
    },
  };
}
