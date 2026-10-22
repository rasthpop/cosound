"""Calibrate retrieval weights and normalization on the dev split (P05.T06).

    uv run python scripts/calibrate.py

Needs every pair of the required dev queries judged: the documented minimum in
data/evaluation/judging_minimum.json when it exists, otherwise the whole dev split. Writes
config/retrieval.calibrated.yaml (a proposal with a new weights_version) and the results table
to docs/calibration.md. Review both, then copy the proposal over config/retrieval.yaml. The test
split is never used here.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

import yaml
from _runtime import build_runtime

from music_discovery.evaluation.calibration import (
    CalibrationError,
    calibrate,
    check_dev_judgments,
    grid,
)
from music_discovery.evaluation.datasets import load_dataset
from music_discovery.infrastructure.settings import get_settings


def main() -> int:
    settings = get_settings()
    dataset = load_dataset(settings.evaluation_dir)
    runtime = build_runtime(settings)
    base = runtime.retriever.config
    minimum = settings.evaluation_dir / "judging_minimum.json"
    required = json.loads(minimum.read_text())["dev"] if minimum.exists() else None
    try:
        excluded = check_dev_judgments(dataset, required)
        trials = calibrate(dataset, runtime.retriever.with_config, base, required=required)
    except CalibrationError as exc:
        print(f"cannot calibrate: {exc}", file=sys.stderr)
        return 1

    best = trials[0]
    today = datetime.now(UTC).date().isoformat()
    proposal = best.config.model_copy(update={"weights_version": f"w1-dev-{today}"})
    out = settings.project_root / "config" / "retrieval.calibrated.yaml"
    out.write_text(
        f"# Proposed by scripts/calibrate.py on {today} (dev split, hybrid nDCG@5 = {best.ndcg}).\n"
        + yaml.safe_dump(proposal.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    table = ["| Rank | Configuration | nDCG@5 (dev) | n |", "|---|---|---|---|"]
    for i, trial in enumerate(trials, start=1):
        score = "—" if trial.ndcg is None else f"{trial.ndcg:.3f}"
        table.append(f"| {i} | {trial.label} | {score} | {trial.n} |")
    doc = settings.project_root / "docs" / "calibration.md"
    text = doc.read_text(encoding="utf-8")
    marker = "## Results"
    head = text.split(marker, 1)[0]
    left_out = f" Unjudged dev queries left out: {', '.join(excluded)}." if excluded else ""
    doc.write_text(
        f"{head}{marker}\n\nRun {today}, {len(grid(base))} configurations.{left_out}\n\n"
        + "\n".join(table)
        + "\n"
    )
    print(f"best: {best.label} -> nDCG@5 {best.ndcg} (n={best.n}); proposal: {out}")
    if excluded:
        print(f"left out (unjudged dev queries): {', '.join(excluded)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
