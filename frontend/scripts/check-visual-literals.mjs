// Ban literal visual values in the views (ADR-0003, ui-design-tokens §6):
//   node scripts/check-visual-literals.mjs [dir ...]   default: src/components src/pages
// Flags hex colours, rgb()/rgba()/hsl()/hsla()/oklch()/oklab() colour functions and Tailwind
// arbitrary values or properties (`bg-[#fff]`, `p-[13px]`, `[color:red]`). Everything visual
// must come from the token utilities generated in src/theme/generated/tokens.css.
// Exit 1 with one line per finding; runs as part of `npm run lint`.
import { readdir, readFile } from "node:fs/promises";
import { extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const EXTENSIONS = new Set([".ts", ".tsx", ".css", ".js", ".jsx", ".mdx"]);

const RULES = [
  { name: "hex colour", pattern: /(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g },
  { name: "colour function", pattern: /\b(?:rgba?|hsla?|oklch|oklab|lab|lch|hwb|color)\(/gi },
  // a Tailwind utility with an arbitrary value: `bg-[#fff]`, `p-[13px]`, `w-[calc(…)]`, `text-[var(--x)]`.
  // Arbitrary *variants* end in `]:` (`data-[state=open]:`, `has-[>svg]:`): they select a state,
  // they set no visual value, so they are allowed.
  { name: "Tailwind arbitrary value", pattern: /(?<![\w$])-?[a-z][\w-]*-\[[^\]\s]+\](?!:)/g },
  // an arbitrary property: `[color:red]`, `[mask-type:luminance]`
  { name: "Tailwind arbitrary property", pattern: /(?<![\w$])\[[a-z][\w-]*:[^\]\s]+\](?!:)/g },
];

/** Findings in one file's text: `{ line, column, rule, match }`. */
export function findLiterals(text) {
  const findings = [];
  const lines = text.split("\n");
  lines.forEach((line, i) => {
    for (const { name, pattern } of RULES) {
      for (const m of line.matchAll(pattern)) {
        findings.push({ line: i + 1, column: (m.index ?? 0) + 1, rule: name, match: m[0] });
      }
    }
  });
  return findings;
}

async function* files(dir) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return; // a missing folder has nothing to check
  }
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* files(path);
    else if (EXTENSIONS.has(extname(entry.name))) yield path;
  }
}

async function main() {
  const args = process.argv.slice(2);
  const dirs = args.length ? args : [join(root, "src/components"), join(root, "src/pages")];
  let count = 0;
  for (const dir of dirs) {
    for await (const path of files(dir)) {
      for (const f of findLiterals(await readFile(path, "utf8"))) {
        count += 1;
        console.error(`${relative(process.cwd(), path)}:${f.line}:${f.column}  ${f.rule}: ${f.match}`);
      }
    }
  }
  if (count > 0) {
    console.error(`\n${count} literal visual value(s). Use token utilities (see src/theme/generated/tokens.css).`);
    process.exit(1);
  }
  console.log("visual literals: none in", dirs.map((d) => relative(process.cwd(), d) || ".").join(", "));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  await main();
}
