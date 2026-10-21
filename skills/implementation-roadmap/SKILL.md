---
name: implementation-roadmap
description: How to execute the phased implementation plan in skills/phases/ — pick the next ready task, load the skills it names, implement it to its "Done when" criteria, and update its status. Load at the start of any implementation session, when asked "what's next", when starting/finishing a task or phase, or when the plan itself needs to change.
---

# Implementation Roadmap

The product spec lives in `base.md` (functional) and, once it exists, the UI/UX plan. The **executable** plan lives in `skills/phases/`:

```
skills/phases/
├── README.md                 # overview, dependency graph, milestone mapping
├── functional/P00…P10-*.md   # backend, ML pipeline, API, frontend data layer
└── ui/U00…U05-*.md           # visual interface (provisional until the UI plan arrives)
```

## Session protocol

1. **Orient.** Run
   ```bash
   python skills/implementation-roadmap/scripts/phase_status.py          # progress + ready tasks
   python skills/implementation-roadmap/scripts/phase_status.py --phase P03
   ```
2. **Pick one task** from "Ready to start" (all dependencies done). Prefer the lowest phase number; P07 (spatial) and the U-phases may run in parallel with their own tracks (see README).
3. **Mark it in progress**: change its `- **Status:** [ ]` to `[~]`.
4. **Load the skills** listed in the task's `Skills:` line, always plus `music-discovery-architecture`.
5. **Implement only that task's scope.** Files listed under `Files:` are the expected footprint; touching other layers is a smell — stop and reconsider.
6. **Verify every `Done when:` bullet** with an actual command (test, script run, checker). Run:
   ```bash
   python skills/music-discovery-architecture/scripts/check_boundaries.py
   uv run pytest -m "not slow"   # once P00 exists
   ```
7. **Mark done** (`[x]`) and add a one-line note under the task if anything diverged from plan (`- **Notes:** …`). If blocked, use `[!]` and say why in Notes.
8. **Phase exit:** when all tasks of a phase are done, check the phase's *Exit criteria* block and tick it. Exit criteria map onto the milestone acceptance criteria in `base.md` §18.

## Task block format (keep it parseable)

```markdown
### P02.T06 — FMA loader, audio probe & import
- **Skills:** fma-audio-corpus, domain-modeling
- **Depends on:** P02.T05, P01.T07
- **Files:** src/music_discovery/ingestion/fma_loader.py, tests/integration/ingestion/test_fma_loader.py
- **Do:**
  - …
- **Done when:**
  - …
- **Status:** [ ]
```

`Depends on:` accepts task IDs (`P01.T04`) and whole phases (`P00` = every task of that phase), or `—` for none. Statuses: `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked · `[-]` deferred (out of the current scope, e.g. post-MVP; does not block dependants).

## Changing the plan

- The plan may be wrong; fix it rather than working around it. Edit the phase file, keep IDs stable (append new tasks with the next free number, never renumber), and run `phase_status.py --check` to validate the dependency graph.
- Any change that alters a **public API contract** must also update P09 (frontend data layer) tasks and be flagged for the UI track — see `api-contracts`.
- When the UI/UX plan arrives, run the `ui-plan-intake` skill; it rewrites `skills/phases/ui/` and may append contract tasks to P08/P09. It must not edit functional tasks other than appending.

## Ground rules that apply to every task

- Never fabricate tracks, links, metadata, or claims (base §8, §13, §20). Missing stays `None`/`null`.
- Never commit secrets or audio files. `data/` and `artifacts/` are git-ignored except manifests and small fixtures.
- Real CLAP/UMAP runs are `@pytest.mark.slow`; unit tests use fakes.
- Don't build ahead: a task does not create modules for later tasks "just in case" (base §4 last paragraph).
