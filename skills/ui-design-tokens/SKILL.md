---
name: ui-design-tokens
description: Design-token and theming architecture for the music discovery interface — token tiers (primitive → semantic → component), naming, color modes, data-visualization scales for the map, motion and density tokens, and how the UI plan's visual vision is encoded so that the whole look can change without touching views' logic. Load when creating or changing anything in frontend/src/theme/, choosing colors/typography/spacing/motion, or reviewing a component for hard-coded visual values.
---

# UI Design Tokens

Spec: `base.md` §1 req. 10, §14.4 last paragraph ("visual presentation, color system, animation, and atmosphere can change without changing the backend or retrieval pipeline"). **Values come from the UI/UX plan.** This skill fixes the *structure* so values are swappable.

## 1. Tiers

```
primitive   →  raw palette & scales        color.violet.500, space.4, font.size.300, duration.200
semantic    →  meaning in this product      color.surface.base, color.text.muted, color.evidence.strong,
                                            color.state.warning, space.card.gap, motion.enter
component   →  per-component overrides      trackCard.background, map.point.radius.selected
```

- Components consume **semantic or component tokens only**, never primitives and never literals.
- Themes (light/dark/high-contrast, or the UI plan's "atmospheres") remap semantic → primitive. A theme switch must not require a component change.

## 2. Files

```
frontend/src/theme/
├── tokens/primitives.ts      # values from the UI plan
├── tokens/semantic.ts        # product meanings; one object per theme
├── tokens/components.ts      # optional overrides
├── scales/categorical.ts     # map / genre color scales (see §4)
├── ThemeProvider.tsx         # sets CSS variables / context; color-mode handling
└── global.css                # resets, font-face, CSS variable defaults
```

Emit tokens as **CSS custom properties** (`--color-surface-base`) so non-React code (deck.gl accessors via a small reader, canvas) can read the same values. Provide a typed accessor `token("color.surface.base")` for TS.

## 3. Semantic token families the product needs regardless of style

| Family | Purpose |
|---|---|
| `surface.*`, `text.*`, `border.*`, `focus.ring` | base UI |
| `state.loading / empty / error / warning / degraded` | system states (see `ux-states-and-evidence`) |
| `evidence.audio_and_metadata / metadata_only / no_audio` | evidence-status badges |
| `match.strong / partial / weak` | match-strength bands (never numeric probabilities) |
| `feedback.positive / negative / neutral` | feedback affordances |
| `map.point.default / hover / selected / dimmed / result` | map point states |
| `motion.duration.* / easing.*` + `motion.reduced` | animation; must honor `prefers-reduced-motion` |
| `density.*` | compact/comfortable spacing sets |

## 4. Map & data-viz scales

- Categorical scale for genres (≥ 8 distinguishable hues + "other"), sequential scale for match strength, both defined in `scales/` from the UI plan's palette. Load the `dataviz` skill when designing them; validate contrast against the map background and color-vision-deficiency safety.
- Colors are returned as `[r, g, b, a]` tuples for deck.gl by a pure helper (`scales/toRgba.ts`) — deck.gl code never parses CSS.
- Encoding rules: color never the *only* channel for state (selected also gets size/outline); legend text comes from data, not hard-coded genre lists.

## 5. Accessibility baselines (independent of the vision)

Text contrast ≥ WCAG AA (4.5:1 body, 3:1 large/UI), visible focus ring token, min hit target 24×24 CSS px (44 recommended for touch), reduced-motion variant for every motion token.

## 6. Review checklist

- [ ] `grep -rnE "#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(" frontend/src/components frontend/src/pages` → no hits.
- [ ] No font family / px sizes in components (tokens or typography components only).
- [ ] Each theme defines every semantic token (type-checked: `satisfies SemanticTokens`).
- [ ] Map colors come from `scales/`, not inline arrays.
