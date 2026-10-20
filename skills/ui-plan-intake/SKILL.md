---
name: ui-plan-intake
description: Procedure for ingesting the separate UI/UX plan (interface settings and visual vision) into the implementation roadmap — read it, map every screen/interaction to the existing hook and API contracts, run a data-gap analysis, raise contract requests to the functional track, and rewrite the provisional U-phases in skills/phases/ui/. Load as soon as the UI/UX plan document is provided, or when that plan changes.
---

# UI Plan Intake

The functional plan (`base.md`) deliberately leaves the interface unspecified. The UI/UX plan will arrive later. The provisional phases `skills/phases/ui/U00–U05` are scaffolding; this skill turns the real plan into real phases **without disturbing the functional track**.

## 1. Inputs

- The UI/UX plan (save it as `ui.md` at the repo root, next to `base.md`, unless the user specifies another path).
- `skills/phases/README.md`, `skills/phases/ui/*.md`
- `skills/api-contracts/SKILL.md` and the current `frontend/openapi.json` (if P08 is done)
- The hook signatures in `skills/phases/functional/P09-frontend-integration-layer.md` (or `frontend/src/hooks/` if implemented)

## 2. Procedure

1. **Read the whole UI plan.** Extract into a working table (`docs/ui/intake.md`):
   - Screens / views / panels, their layout zones and responsive behavior.
   - Interactions (search, plate browsing, feedback gestures, map pan/zoom/select/hover, transitions, audio preview).
   - Visual system: palette, typography, motion, atmosphere, iconography, density, dark/light.
   - Accessibility and platform targets (browsers, mobile, keyboard).
   - Technology preferences (styling lib, component workbench, animation lib).
2. **Map every element to data.** For each screen element, name the hook field / event that feeds it (e.g. "plate card subtitle ← `TrackResult.artists`", "map point color ← `MapPoint.genre` via token scale"). Mark each mapping ✅ available, 🟡 derivable by formatting only, ❌ missing.
3. **Gap analysis.** For every ❌:
   - If it is presentation-only (e.g. a label for an enum) → UI task.
   - If it needs data or logic (e.g. "cluster names on the map", "why this changed", "waveform preview") → **contract request**: append a task to P08 (backend DTO/service) and P09 (hook) using the next free task numbers, `Depends on:` the relevant functional tasks, and reference it from the UI task. Never plan a UI-side workaround that computes domain data.
   - If it conflicts with a functional rule (e.g. "show % flute probability", "rank by map distance", "show audio for tracks without licensed audio") → record as a **conflict** and ask the user; the functional rule wins until they decide.
4. **Choose technology** (ADR `docs/adr/00xx-ui-stack.md`): styling approach, workbench (Storybook vs Ladle), animation library, icon set, font loading. Respect the folder/import contract in `ui-architecture`.
5. **Rewrite the U-phases.** Replace the provisional content in `skills/phases/ui/` keeping:
   - IDs `U00…` (U00 becomes "done" once intake is complete); add phases if needed (U06…); keep the task block format from `implementation-roadmap`.
   - Each task names `Skills:` (at least `ui-architecture` + the relevant UI skill), `Files:` only under `theme/`, `components/`, `pages/`, `App.tsx`, `docs/ui/`, plus fixtures if a new mock state is needed.
   - Dependencies on functional tasks are explicit (e.g. `U04.T02` depends on `P09.T05`). UI tasks that only need fixtures depend on `P09.T02` (mocks), not on the live backend.
6. **Validate:** `python skills/implementation-roadmap/scripts/phase_status.py --check`.
7. **Summarize to the user:** new U-phase list, contract requests added to P08/P09, conflicts needing a decision, and the stack ADR.

## 3. Guardrails

- Intake never edits existing functional tasks — it only **appends** contract-request tasks.
- Visual requirements never change backend semantics. If the vision implies a different meaning (e.g. map distance = similarity), the UI must label it honestly (see `ux-states-and-evidence`).
- Keep the UI plan's vocabulary in `docs/ui/glossary.md` so component names match the plan.
