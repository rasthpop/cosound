// Generate src/api/generated.ts from openapi.json (written by scripts/export_openapi.py).
//   node scripts/contract.mjs           write the file
//   node scripts/contract.mjs --check   exit 1 if the committed file is stale
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import openapiTS, { astToString } from "openapi-typescript";

const root = new URL("../", import.meta.url);
const schemaUrl = new URL("openapi.json", root);
const outputPath = fileURLToPath(new URL("src/api/generated.ts", root));

// defaultNonNullable: false keeps fields with server defaults optional in requests
const ast = await openapiTS(schemaUrl, { alphabetize: true, defaultNonNullable: false });
const banner =
  "/**\n * Generated from frontend/openapi.json by scripts/contract.mjs (openapi-typescript).\n" +
  " * Do not edit: change the backend DTOs, run `make contract`, then `npm run contract`.\n */\n\n";
const generated = banner + astToString(ast);

if (process.argv.includes("--check")) {
  const current = await readFile(outputPath, "utf8").catch(() => "");
  if (current !== generated) {
    console.error("src/api/generated.ts is out of date with openapi.json; run `npm run contract`.");
    process.exit(1);
  }
  console.log("contract: generated.ts matches openapi.json");
} else {
  await writeFile(outputPath, generated);
  console.log(`wrote ${outputPath}`);
}
