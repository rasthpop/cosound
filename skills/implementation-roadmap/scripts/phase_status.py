#!/usr/bin/env python3
"""Report progress across the phase plans in skills/phases/.

Parses task blocks of the form

    ### P02.T03 — Title
    - **Depends on:** P01.T02, P02.T01      (or "—")
    - **Status:** [ ]                         ([ ] todo, [~] in progress, [x] done, [!] blocked)

and prints per-phase progress plus the tasks that are ready to start
(todo, with every dependency done).

Usage:
    python skills/implementation-roadmap/scripts/phase_status.py \
        [--phases-dir DIR] [--phase P03] [--ready] [--check]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

TASK_RE = re.compile(r"^###\s+((?:P|U)\d{2}\.T\d{2})\s*[—-]\s*(.+?)\s*$")
DEPS_RE = re.compile(r"^\s*-\s*\*\*Depends on:\*\*\s*(.*)$")
STATUS_RE = re.compile(r"^\s*-\s*\*\*Status:\*\*\s*\[(.)\]")
ID_RE = re.compile(r"\b(?:P|U)\d{2}\.T\d{2}\b")
PHASE_DEP_RE = re.compile(r"\b((?:P|U)\d{2})\b(?!\.T)")

STATUS_NAMES = {" ": "todo", "~": "in-progress", "x": "done", "X": "done", "!": "blocked"}


@dataclass
class Task:
    id: str
    title: str
    file: Path
    deps: list[str] = field(default_factory=list)
    phase_deps: list[str] = field(default_factory=list)
    status: str = "todo"

    @property
    def phase(self) -> str:
        return self.id.split(".")[0]


def parse(phases_dir: Path) -> dict[str, Task]:
    tasks: dict[str, Task] = {}
    for file in sorted(phases_dir.rglob("*.md")):
        current: Task | None = None
        for line in file.read_text(encoding="utf-8").splitlines():
            if m := TASK_RE.match(line):
                current = Task(m.group(1), m.group(2), file)
                if current.id in tasks:
                    print(f"duplicate task id {current.id} in {file}", file=sys.stderr)
                tasks[current.id] = current
                continue
            if current is None:
                continue
            if m := DEPS_RE.match(line):
                current.deps = ID_RE.findall(m.group(1))
                current.phase_deps = PHASE_DEP_RE.findall(ID_RE.sub("", m.group(1)))
            elif m := STATUS_RE.match(line):
                current.status = STATUS_NAMES.get(m.group(1), "todo")
    return tasks


def is_ready(t: Task, tasks: dict[str, Task]) -> bool:
    if t.status != "todo":
        return False
    for d in t.deps:
        if d not in tasks or tasks[d].status != "done":
            return False
    for p in t.phase_deps:  # a bare phase id means "every task of that phase"
        if any(o.phase == p and o.status != "done" for o in tasks.values()):
            return False
    return True


def main() -> int:
    default_dir = Path(__file__).resolve().parents[2] / "phases"
    ap = argparse.ArgumentParser()
    ap.add_argument("--phases-dir", type=Path, default=default_dir)
    ap.add_argument("--phase", help="only show this phase (e.g. P03, U01)")
    ap.add_argument("--ready", action="store_true", help="only list ready tasks")
    ap.add_argument("--check", action="store_true", help="validate dependency ids and exit")
    args = ap.parse_args()

    tasks = parse(args.phases_dir)
    if not tasks:
        print(f"no tasks found under {args.phases_dir}")
        return 1

    phases = sorted({t.phase for t in tasks.values()})
    errors = [
        f"{t.id}: unknown dependency {d}"
        for t in tasks.values()
        for d in [*t.deps, *t.phase_deps]
        if d not in tasks and d not in phases
    ]
    if args.check or errors:
        for e in errors:
            print(e)
        if args.check:
            print("dependency graph OK" if not errors else f"{len(errors)} error(s)")
            return 1 if errors else 0

    selected = [t for t in tasks.values() if not args.phase or t.phase == args.phase]

    if not args.ready:
        print(f"{'phase':<6} {'done':>4}/{'all':<4} {'wip':>3} {'blk':>3}  file")
        for p in phases:
            if args.phase and p != args.phase:
                continue
            pts = [t for t in tasks.values() if t.phase == p]
            done = sum(t.status == "done" for t in pts)
            wip = sum(t.status == "in-progress" for t in pts)
            blk = sum(t.status == "blocked" for t in pts)
            print(f"{p:<6} {done:>4}/{len(pts):<4} {wip:>3} {blk:>3}  {pts[0].file.name}")
        wip_tasks = [t for t in selected if t.status == "in-progress"]
        if wip_tasks:
            print("\nIn progress:")
            for t in wip_tasks:
                print(f"  {t.id}  {t.title}")
        print()

    ready = [t for t in selected if is_ready(t, tasks)]
    print("Ready to start:" if ready else "No task is ready (check blocked/in-progress tasks).")
    for t in sorted(ready, key=lambda t: t.id):
        print(f"  {t.id}  {t.title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
