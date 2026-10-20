# U00 — UI/UX Plan Intake

**Goal:** turn the separate UI/UX plan into concrete U-phases that fit the existing functional contracts, with explicit contract requests for any missing data and no edits to functional tasks.
**Inputs:** the UI/UX plan (expected at `ui.md`), `base.md` §14, the P08/P09 contract.
**Depends on:** the UI/UX plan document existing. Functional phases are **not** blocked by U00.

> Everything in U01–U05 is **provisional scaffolding** describing work any UI plan will require. U00.T04 rewrites it.

### U00.T01 — Receive & map the UI/UX plan
- **Skills:** ui-plan-intake, ui-architecture
- **Depends on:** —
- **Files:** ui.md, docs/ui/intake.md, docs/ui/glossary.md
- **Do:**
  - Save the plan; extract screens, interactions, visual system, accessibility/platform targets, tech preferences; map every element to hook fields/events (✅ / 🟡 / ❌).
- **Done when:**
  - `docs/ui/intake.md` has a complete element → data mapping table.
- **Notes:** waiting for the UI/UX plan.
- **Status:** [!]

### U00.T02 — Gap analysis & contract requests
- **Skills:** ui-plan-intake, api-contracts, ux-states-and-evidence
- **Depends on:** U00.T01
- **Files:** docs/ui/intake.md, skills/phases/functional/P08-application-and-api.md (append only), skills/phases/functional/P09-frontend-integration-layer.md (append only)
- **Do:**
  - For each ❌: classify as presentation-only, contract request (append P08/P09 tasks), or conflict with a functional rule (escalate to the user).
- **Done when:**
  - Every ❌ resolved into a task or a recorded user decision; `phase_status.py --check` passes.
- **Status:** [ ]

### U00.T03 — UI stack ADR
- **Skills:** ui-plan-intake, ui-design-tokens, ui-isolated-development
- **Depends on:** U00.T01
- **Files:** docs/adr/0003-ui-stack.md
- **Do:**
  - Decide styling approach, workbench (Storybook/Ladle), animation library, icons, font loading, routing; confirm compatibility with the folder/import contract.
- **Done when:**
  - ADR accepted by the user.
- **Status:** [ ]

### U00.T04 — Rewrite U-phases from the plan
- **Skills:** ui-plan-intake, implementation-roadmap
- **Depends on:** U00.T02, U00.T03
- **Files:** skills/phases/ui/*.md, skills/phases/README.md
- **Do:**
  - Replace provisional U01–U05 content with plan-specific tasks (keep IDs/format; add U06+ if needed); dependencies on P09 tasks explicit; update the phases README table and graph.
- **Done when:**
  - `phase_status.py --check` passes; user has reviewed the new UI phases.
- **Status:** [ ]

## Exit criteria
- [ ] UI phases reflect the UI/UX plan; contract requests and conflicts are tracked; stack decided.
