# U00 — UI/UX Plan Intake

**Goal:** turn the separate UI/UX plan into concrete U-phases that fit the existing functional contracts, with explicit contract requests for any missing data and no edits to functional tasks.
**Inputs:** the UI/UX plan (`skills/phases/ui/ui.md`), `base.md` §14, the P08/P09 contract.
**Depends on:** the UI/UX plan document existing. Functional phases are **not** blocked by U00.

> U01–U05 were rewritten from the plan by U00.T04 (2026-10-26). Outputs: `docs/ui/intake.md`, `docs/ui/glossary.md`, `docs/adr/0003-ui-stack.md`.

### U00.T01 — Receive & map the UI/UX plan
- **Skills:** ui-plan-intake, ui-architecture
- **Depends on:** —
- **Files:** skills/phases/ui/ui.md, docs/ui/intake.md, docs/ui/glossary.md
- **Do:**
  - Save the plan; extract screens, interactions, visual system, accessibility/platform targets, tech preferences; map every element to hook fields/events (✅ / 🟡 / ❌).
- **Done when:**
  - `docs/ui/intake.md` has a complete element → data mapping table.
- **Notes:** The plan stays at `skills/phases/ui/ui.md`, where the project owner put it, not at the repo root. Mapping: `docs/ui/intake.md` §2 (every element of ui.md §4 marked ✅/🟡/❌) and §3 (states → fixtures/scenarios).
- **Status:** [x]

### U00.T02 — Gap analysis & contract requests
- **Skills:** ui-plan-intake, api-contracts, ux-states-and-evidence
- **Depends on:** U00.T01
- **Files:** docs/ui/intake.md, skills/phases/functional/P08-application-and-api.md (append only), skills/phases/functional/P09-frontend-integration-layer.md (append only)
- **Do:**
  - For each ❌: classify as presentation-only, contract request (append P08/P09 tasks), or conflict with a functional rule (escalate to the user).
- **Done when:**
  - Every ❌ resolved into a task or a recorded user decision; `phase_status.py --check` passes.
- **Notes:** Seven ❌ groups (intake §4): six contract requests appended as P08.T10–T12 and P09.T10–T12, and one conflict, D1 (chip removal vs Agent C semantics and the hard-constraint invariant). D1 is recorded with the functional rule as the default until the owner decides; D2–D5 settle the ui.md §9 questions.
- **Status:** [x]

### U00.T03 — UI stack ADR
- **Skills:** ui-plan-intake, ui-design-tokens, ui-isolated-development
- **Depends on:** U00.T01
- **Files:** docs/adr/0003-ui-stack.md
- **Do:**
  - Decide styling approach, workbench (Storybook/Ladle), animation library, icons, font loading, routing; confirm compatibility with the folder/import contract.
- **Done when:**
  - ADR accepted by the user.
- **Notes:** ADR-0003: Tailwind v4 themed only through token CSS variables, shadcn/ui in `components/ui/`, deck.gl 9.4, vaul, motion, lucide, Inter, Storybook 10. Status Proposed; the owner accepts it by merging the U00 PR.
- **Status:** [x]

### U00.T04 — Rewrite U-phases from the plan
- **Skills:** ui-plan-intake, implementation-roadmap
- **Depends on:** U00.T02, U00.T03
- **Files:** skills/phases/ui/*.md, skills/phases/README.md
- **Do:**
  - Replace provisional U01–U05 content with plan-specific tasks (keep IDs/format; add U06+ if needed); dependencies on P09 tasks explicit; update the phases README table and graph.
- **Done when:**
  - `phase_status.py --check` passes; user has reviewed the new UI phases.
- **Notes:** U01–U05 rewritten against ui.md; U02.T07 added for views that need the contract additions. The owner reviews them in the U00 PR.
- **Status:** [x]

## Exit criteria
- [x] UI phases reflect the UI/UX plan; contract requests and conflicts are tracked; stack decided.
