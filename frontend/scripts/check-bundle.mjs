// The production bundle is the interface only: no MSW, no mock worker, no dev harness (P09.T09,
// U04.T05). Runs after `vite build` as part of `npm run build`; exits 1 with one line per finding.
//   node scripts/check-bundle.mjs [distDir]   default: dist
import { readdir, readFile } from "node:fs/promises";
import { extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const dist = process.argv[2] ?? join(root, "dist");

/** Text that only the mocks or the harness put in a bundle. */
const MARKERS = [
  { name: "MSW worker setup", pattern: /setupWorker|mockServiceWorker/ },
  { name: "mock scenarios", pattern: /\[mocks\] API mocked/ },
  { name: "dev contract harness", pattern: /contract harness/i },
];
const FORBIDDEN_FILES = new Set(["mockServiceWorker.js"]);
const TEXT = new Set([".js", ".mjs", ".css", ".html", ".map"]);

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(path);
    else yield path;
  }
}

const findings = [];
for await (const path of walk(dist)) {
  const name = relative(dist, path);
  if (FORBIDDEN_FILES.has(name.split(/[\\/]/).at(-1))) findings.push(`${name}: mock-only file`);
  if (!TEXT.has(extname(path))) continue;
  const text = await readFile(path, "utf8");
  for (const { name: marker, pattern } of MARKERS) if (pattern.test(text)) findings.push(`${name}: ${marker}`);
}
if (findings.length) {
  console.error(findings.join("\n"));
  console.error(`\nThe production bundle contains mock or dev-only code (${findings.length} finding(s)).`);
  process.exit(1);
}
console.log("bundle: no mocks, no dev harness in", relative(process.cwd(), dist) || ".");
