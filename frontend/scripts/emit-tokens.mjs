// Emit src/theme/generated/tokens.css from the TypeScript tokens (ADR-0003, "How tokens reach
// Tailwind"):
//   node scripts/emit-tokens.mjs           write the file
//   node scripts/emit-tokens.mjs --check   exit 1 if the committed file is stale
//
// The file has three parts:
// 1. One block of `--token-*` custom properties per theme. Dark is also `:root`, so it applies
//    before the ThemeProvider sets `data-theme`. Motion is the same in every theme, so it has its
//    own `:root` block, which the reduced-motion values replace under `prefers-reduced-motion`
//    (same specificity, later in the file).
// 2. A `@theme` block that resets Tailwind's default namespaces, so `bg-red-500` or `text-xl`
//    do not exist.
// 3. A `@theme inline` block that maps utility names to the semantic `--token-*` variables only.
// The `--token-` prefix keeps the theme values apart from Tailwind's own `--color-*` names.
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { runnerImport } from "vite";

const root = new URL("../", import.meta.url);
const outputPath = fileURLToPath(new URL("src/theme/generated/tokens.css", root));
const { module: semantic } = await runnerImport(fileURLToPath(new URL("src/theme/tokens/semantic.ts", root)));
const { themes, DEFAULT_THEME } = semantic;

const kebab = (s) => s.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();

/** Units by token path: px for sizes, ms for durations, unitless for the rest. */
function cssValue(path, value) {
  if (typeof value === "string") return value;
  if (path[0] === "opacity" || path.at(-1) === "weight") return String(value);
  if (path[0] === "motion" && path.includes("duration")) return `${value}ms`;
  return `${value}px`;
}

/** Flatten a token object into [name, value] pairs. Booleans (e.g. `motion.*.pulse`) are skipped. */
function flatten(obj, path = []) {
  return Object.entries(obj).flatMap(([key, value]) => {
    const next = [...path, key];
    if (typeof value === "object" && value !== null) return flatten(value, next);
    if (typeof value === "boolean") return [];
    return [[`--token-${next.map(kebab).join("-")}`, cssValue(next, value)]];
  });
}

/** Per-theme variables: everything except motion. */
function themeVariables(tokens) {
  const { motion: _motion, ...rest } = tokens;
  return flatten(rest);
}

const block = (selector, vars, extra = []) =>
  [`${selector} {`, ...extra.map((l) => `  ${l}`), ...vars.map(([n, v]) => `  ${n}: ${v};`), "}"].join("\n");

// Utility name -> semantic token variable. Only semantic tokens reach Tailwind.
const COLOR_UTILITIES = {
  "surface-canvas": "color-surface-canvas",
  "surface-panel": "color-surface-panel",
  "surface-raised": "color-surface-raised",
  fg: "color-text-default",
  muted: "color-text-muted",
  "on-accent": "color-text-on-accent",
  hairline: "color-border-hairline",
  "border-strong": "color-border-strong",
  focus: "color-focus-ring",
  accent: "color-accent-default",
  "accent-hover": "color-accent-hover",
  "accent-subtle": "color-accent-subtle",
  "state-loading": "color-state-loading",
  "state-empty": "color-state-empty",
  "state-error": "color-state-error",
  "state-warning": "color-state-warning",
  "state-degraded": "color-state-degraded",
  "evidence-audio-and-metadata": "color-evidence-audio-and-metadata",
  "evidence-metadata-only": "color-evidence-metadata-only",
  "evidence-no-audio": "color-evidence-no-audio",
  "match-strong": "color-match-strong",
  "match-partial": "color-match-partial",
  "match-weak": "color-match-weak",
  "feedback-positive": "color-feedback-positive",
  "feedback-negative": "color-feedback-negative",
  "feedback-neutral": "color-feedback-neutral",
  "map-backdrop": "color-map-backdrop",
};

const TEXT_SIZES = ["meta", "body", "heading", "display"];

function utilityMappings(tokens) {
  const v = (name) => `var(--token-${name})`;
  const lines = [
    ...Object.entries(COLOR_UTILITIES).map(([u, t]) => [`--color-${u}`, v(t)]),
    ["--font-sans", v("font-family-sans")],
    ...TEXT_SIZES.flatMap((s) => [
      [`--text-${s}`, v(`font-size-${s}`)],
      [`--text-${s}--line-height`, v(`font-line-height-${s}`)],
    ]),
    ...Object.keys(tokens.font.weight).map((w) => [`--font-weight-${kebab(w)}`, v(`font-weight-${kebab(w)}`)]),
    ...Object.keys(tokens.radius).map((r) => [`--radius-${r}`, v(`radius-${r}`)]),
    ["--blur-panel", v("blur-panel")],
    ["--ease-out", v("motion-easing-out")],
    ["--ease-linear", v("motion-easing-linear")],
    // 8 px grid: p-1 = 8px, p-0.5 = 4px, p-2 = 16px
    ["--spacing", v("space-sm")],
  ];
  return lines;
}

// Tailwind namespaces whose defaults are removed. Breakpoints stay (layout, not visual style).
const RESET = [
  "--color-*",
  "--font-*",
  "--text-*",
  "--font-weight-*",
  "--leading-*",
  "--tracking-*",
  "--radius-*",
  "--shadow-*",
  "--inset-shadow-*",
  "--drop-shadow-*",
  "--text-shadow-*",
  "--blur-*",
  "--ease-*",
  "--animate-*",
  "--perspective-*",
  "--aspect-*",
];

function render() {
  const names = Object.keys(themes);
  const ordered = [DEFAULT_THEME, ...names.filter((n) => n !== DEFAULT_THEME)];
  const { motion } = themes[DEFAULT_THEME];
  const reduced = flatten(motion.reduced, ["motion"]);
  const parts = [
    "/* Generated from src/theme/tokens by scripts/emit-tokens.mjs. Do not edit: change the tokens,",
    "   then run `npm run tokens`. */",
    "",
    ...ordered.flatMap((name) => {
      const selector = name === DEFAULT_THEME ? `:root,\n:root[data-theme="${name}"]` : `:root[data-theme="${name}"]`;
      return [block(selector, themeVariables(themes[name]), [`color-scheme: ${name};`]), ""];
    }),
    block(":root", flatten(motion.default, ["motion"])),
    "",
    "@media (prefers-reduced-motion: reduce) {",
    block("  :root", reduced).split("\n").map((l, i) => (i === 0 ? l : `  ${l}`)).join("\n"),
    "}",
    "",
    block("@theme", RESET.map((r) => [r, "initial"])),
    "",
    block("@theme inline", utilityMappings(themes[DEFAULT_THEME])),
    "",
  ];
  return parts.join("\n");
}

const css = render();
if (process.argv.includes("--check")) {
  const current = await readFile(outputPath, "utf8").catch(() => "");
  if (current !== css) {
    console.error("src/theme/generated/tokens.css is out of date with src/theme/tokens; run `npm run tokens`.");
    process.exit(1);
  }
  console.log("tokens: tokens.css matches src/theme/tokens");
} else {
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, css);
  console.log(`wrote ${outputPath}`);
}
