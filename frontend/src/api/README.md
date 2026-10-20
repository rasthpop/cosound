# api/ — functional track

Typed HTTP access to the backend: `client.ts` (requests, cancellation, error normalization, base URL), `generated.ts` (from `openapi.json`) and `types.ts` (friendly aliases only).

- This is the **only** place that calls `fetch`.
- May import: `api/` only.
- No ranking, CLAP, or business rules (base.md §14.1).

Implemented in P09.T01 and P09.T03. Skill: `api-contracts`.
