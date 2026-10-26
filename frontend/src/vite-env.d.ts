/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "mock" serves the API from MSW fixtures (npm run dev:mock). */
  readonly VITE_API_MODE?: "mock" | "live";
  /** Backend origin, e.g. "http://127.0.0.1:8000"; empty = same origin (dev proxy). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
