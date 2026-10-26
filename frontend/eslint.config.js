// Import boundaries mirror skills/music-discovery-architecture (the Python checker is the source of truth).
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

const layer = (name) => [`@/${name}`, `@/${name}/*`, `**/${name}`, `**/${name}/*`];

const deckGl = {
  group: ["@deck.gl/*", "deck.gl", "@luma.gl/*"],
  message: "deck.gl may only be imported under src/components/map/.",
};
const apiClient = {
  group: ["@/api/client", "**/api/client"],
  message: "Only hooks call the API client. Views receive data through props.",
};
const forbid = (layers, message) => ({ group: layers.flatMap(layer), message });

const restrict = (...patterns) => ["error", { patterns }];
const noFetch = [
  "error",
  { name: "fetch", message: "Network calls belong in src/api/client.ts." },
  { name: "XMLHttpRequest", message: "Network calls belong in src/api/client.ts." },
  { name: "EventSource", message: "Network calls belong in src/api/client.ts." },
];

export default tseslint.config(
  { ignores: ["dist", "coverage", "node_modules", "src/api/generated.ts", "playwright-report", "test-results", "public/mockServiceWorker.js"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: { ...reactHooks.configs.recommended.rules },
  },
  {
    files: ["src/api/**"],
    rules: {
      "no-restricted-imports": restrict(
        forbid(["hooks", "components", "pages", "theme", "mocks"], "api/ must not depend on other frontend layers."),
      ),
    },
  },
  {
    files: ["src/hooks/**"],
    rules: {
      "no-restricted-imports": restrict(
        deckGl,
        forbid(["components", "pages", "theme", "mocks"], "Hooks expose state and actions only; no views or styling."),
      ),
      "no-restricted-globals": noFetch,
    },
  },
  {
    files: ["src/mocks/**"],
    rules: {
      "no-restricted-imports": restrict(
        forbid(["hooks", "components", "pages", "theme"], "Mocks mirror the API contract only."),
      ),
    },
  },
  {
    files: ["src/theme/**"],
    rules: {
      "no-restricted-imports": restrict(
        forbid(["api", "hooks", "components", "pages", "mocks"], "theme/ holds design tokens only."),
      ),
      "no-restricted-globals": noFetch,
    },
  },
  {
    files: ["src/components/**"],
    rules: {
      "no-restricted-imports": restrict(
        deckGl,
        apiClient,
        forbid(["hooks", "pages", "mocks"], "Views are pure: props in, events out."),
      ),
      "no-restricted-globals": noFetch,
    },
  },
  {
    files: ["src/components/map/**"],
    rules: {
      "no-restricted-imports": restrict(
        apiClient,
        forbid(["hooks", "pages", "mocks"], "Views are pure: props in, events out."),
      ),
    },
  },
  {
    files: ["src/pages/**"],
    rules: {
      "no-restricted-imports": restrict(deckGl, apiClient, forbid(["mocks"], "Containers use hooks, not mocks.")),
      "no-restricted-globals": noFetch,
    },
  },
  {
    files: ["**/*.test.{ts,tsx}", "**/*.stories.tsx", "test/**"],
    rules: { "no-restricted-imports": "off", "no-restricted-globals": "off" },
  },
  {
    files: ["*.config.{js,ts}"],
    languageOptions: { globals: globals.node },
  },
);
