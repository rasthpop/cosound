# Semantic Music Discovery

Natural-language music discovery (Discogs metadata + CLAP audio semantics + hybrid ranking + 3 agents + UMAP map).

- Functional spec: `base.md`. UI/UX spec: arrives separately (save as `ui.md`, then run the `ui-plan-intake` skill).
- Agent LLMs (optional): OpenRouter free models — https://openrouter.ai/collections/free-models (skill `openrouter-llm`). Model IDs only in config.
- Executable plan: `skills/phases/` — check progress with `python skills/implementation-roadmap/scripts/phase_status.py`.
- Always load `implementation-roadmap` + `music-discovery-architecture` before implementing a task; load the skills listed on the task.

## Non-negotiables
- One task at a time; update its `Status:` line (`[~]` → `[x]`).
- Layer boundaries are enforced: `python skills/music-discovery-architecture/scripts/check_boundaries.py` must pass.
- The visual layer (`frontend/src/{theme,components,pages}`) is isolated from the functional system; it only consumes hooks and `api/types.ts`. Missing data → contract request, never a UI workaround.
- Never fabricate tracks, links, metadata or audio claims. Missing values stay `null`/`None` — never 0.
- Never send secrets, user identifiers or catalog dumps to an LLM (free providers may train on inputs).
- No secrets, audio files, checkpoints or large artifacts in git. No live Discogs calls in tests.
