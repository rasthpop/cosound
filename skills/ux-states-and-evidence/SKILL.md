---
name: ux-states-and-evidence
description: UX rules for system states and honest evidence presentation in the music discovery interface — the complete state matrix (idle, loading, stale, empty, no-confident-match, needs-clarification, degraded semantic/map/LLM, error, offline), how to show interpreted queries, scores, match reasons, uncertainty and "what changed" after feedback without overstating what the system knows, and feedback affordances. Load when designing or reviewing any view that shows search results, track details, feedback, or the map.
---

# UX States & Evidence Presentation

Spec: `base.md` §8, §9.4, §13 (null preservation), §16 (graceful degradation), §20 (no unsupported claims). The UI plan decides *how it looks*; this skill decides *what must be communicated*.

## 1. State matrix (every server-data view handles all that apply)

| State | Source signal | Must communicate |
|---|---|---|
| idle | no query yet | what the user can do (example queries from the UI plan) |
| loading | hook `status="loading"` | progress without layout jump; keep previous results visible but marked stale on refinement |
| stale-response guard | hook drops out-of-order responses | nothing visible — but never flash old results |
| ok | `outcome="ok"` | the plate in **API order** |
| empty | `results=[]`, `outcome="ok"` | nothing matched; suggest broadening |
| no confident match | `outcome="no_confident_match"` | constraints couldn't be satisfied; show which constraints; offer to relax them **as a user choice** |
| needs clarification | `outcome="needs_clarification"` | the `clarification_question`; input to answer |
| degraded: semantic | `capabilities.semantic="unavailable"` | "Sound-based matching is unavailable; results use catalog data only" |
| degraded: map | `capabilities.map="unavailable"` / map 503 | map area explains it's unavailable; search unaffected |
| degraded: LLM | `llm_interpreter="fallback"` | usually silent; optional subtle note in interpreted-query panel |
| error | error envelope | human message by `error.code`, retry action; no stack traces |
| offline / network | client error normalization | retry, preserve typed query |

Build each state once as a view variant and keep them in the workbench (`ui-isolated-development`).

## 2. Interpreted query

Show what the system understood (`interpreted_query`): preferences as removable/editable chips, hard constraints visually distinct from soft preferences, negatives distinct from positives. Editing a chip emits a typed feedback event (`MORE_OF_ATTRIBUTE` / `LESS_OF_ATTRIBUTE`) — the UI never edits the spec locally.

## 3. Results & evidence

- **Order = API order.** Never re-sort client-side by any score.
- `score` is for ordering; if displayed at all, show **bands** ("strong / partial match") from `match_reasons`/semantic band, not "82 %".
- `description` and `match_reasons` are shown as provided; empty description ⇒ show nothing (no placeholder prose).
- `evidence_status` / `uncertainty_flags` are always visible in some form: e.g. "No audio analysis — matched on catalog data", "Vocals not verified".
- `null` fields render as absent, not "Unknown artist" invented text — unless the UI plan defines a neutral placeholder token like "—".
- Links (`source_url`, `preview_url`) render only when non-null; external links open safely (`rel="noopener noreferrer"`). MVP attribution: FMA metadata is CC BY 4.0 (credit the FMA dataset) and each track shows its own license next to playback. Discogs attribution (post-MVP) follows the terms recorded in `docs/data-sources.md`.
- Score breakdown (if the UI plan exposes it) shows missing signals as "not available", never as 0.

## 4. Feedback UX

- Map each gesture to exactly one API event type (`MORE_LIKE_THIS`, `LESS_LIKE_THIS`, `NOT_RELEVANT`, `WRONG_INSTRUMENT`, `MORE_OF_ATTRIBUTE`, `LESS_OF_ATTRIBUTE`, `SELECT_TRACK`). `WRONG_INSTRUMENT` / `*_OF_ATTRIBUTE` need an attribute picker fed from the interpreted query.
- Optimistic UI only for the gesture acknowledgment; the plate updates from the server response.
- After refinement, show **what changed** (`change_summary`) and keep the original query visible; allow undo only if the API supports it (it doesn't initially — don't fake it).

## 5. Map UX

- Make clear the map is a **visual overview**; nearness is suggestive. Neighbors in details come from the API.
- Results without coordinates are listed as "not on the map".
- Selecting on the map and selecting in the plate are the same action (`SELECT_TRACK` / details open) — keep them in sync via the container.

## 6. Accessibility

Keyboard path for everything (search → results → feedback → details → map alternative list), live region for result/refinement announcements, focus management on panel open/close, reduced-motion respect, contrast via tokens.

## 7. Review checklist

- [ ] All applicable states rendered and in the workbench.
- [ ] No percentages/probabilities; no claims beyond `description`/`match_reasons`.
- [ ] Nulls render as absent; no fabricated links or placeholders implying data.
- [ ] Feedback gestures map 1:1 to typed events.
- [ ] Degraded modes visibly explained; search usable without the map.
