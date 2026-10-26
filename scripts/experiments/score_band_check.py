"""Precision of candidate metadata-band thresholds on the dev split (P08.T10).

The same procedure as the semantic bands in docs/calibration.md ("Description strength
threshold"): Agent A deterministic specs for the judged dev queries, hybrid mode over the whole
20-track corpus, and every returned track's normalized metadata score paired with the owner's
`overall_relevance` (relevant = >= 2). The test split is never read.

    uv run python scripts/experiments/score_band_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _runtime import build_runtime

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.evaluation.datasets import load_dataset
from music_discovery.infrastructure.settings import get_settings

THRESHOLDS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3)


def main() -> int:
    settings = get_settings()
    dataset = load_dataset(settings.evaluation_dir)
    minimum = json.loads((settings.evaluation_dir / "judging_minimum.json").read_text())
    query_ids: list[str] = minimum["dev"]
    if dataset.split is None or not set(query_ids) <= set(dataset.split.of("dev")):
        print("judging_minimum dev queries are not all in the dev split", file=sys.stderr)
        return 2
    runtime = build_runtime(settings)
    agent = QueryAgent(load_lexicon())
    corpus = [m.track_id for m in dataset.manifest]
    to_fma = {m.track_id: m.fma_track_id for m in dataset.manifest}

    pairs: list[tuple[float | None, bool]] = []
    for query_id in query_ids:
        spec = agent.interpret(dataset.query(query_id).text)
        result = runtime.retriever.retrieve(spec, mode="hybrid", limit=len(corpus), corpus=corpus)
        relevance = dataset.relevance(query_id)
        for c in result.outcome.candidates:
            grade = relevance.get(to_fma[c.track_id])
            if grade is not None:
                pairs.append((c.score.metadata, grade >= 2))

    scored = [(m, rel) for m, rel in pairs if m is not None]
    base = sum(rel for _, rel in pairs) / len(pairs)
    print(f"{len(pairs)} judged pairs, {len(scored)} with a metadata score, base rate {base:.2f}")
    print("| Band rule | Precision (relevant) | n |\n|---|---|---|")
    for tau in THRESHOLDS:
        above = [rel for m, rel in scored if m >= tau]
        if above:
            print(f"| metadata >= {tau:.2f} | {sum(above) / len(above):.2f} | {len(above)} |")
    for lo, hi in ((0.0, 0.0), (0.0, 0.3), (0.3, 0.6)):
        band = [rel for m, rel in scored if (m == 0.0 if hi == 0.0 else lo < m < hi)]
        if band:
            label = "metadata = 0" if hi == 0.0 else f"{lo:.1f} < metadata < {hi:.1f}"
            print(f"| {label} | {sum(band) / len(band):.2f} | {len(band)} |")
    missing = [rel for m, rel in pairs if m is None]
    if missing:
        print(f"| metadata null | {sum(missing) / len(missing):.2f} | {len(missing)} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
