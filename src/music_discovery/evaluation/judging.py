"""Human relevance judging support (base.md §12.3, data/evaluation/JUDGING.md).

The order of (query, track) pairs is shuffled with a fixed seed and already-judged pairs are
skipped, so judging can stop and resume at any time. System scores are never involved.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from music_discovery.evaluation.datasets import (
    JUDGMENT_COLUMNS,
    EvalDataset,
    EvalQuery,
    Judgment,
    ManifestEntry,
)


@dataclass(frozen=True)
class Pair:
    query: EvalQuery
    track: ManifestEntry


def asked_fields(query: EvalQuery) -> list[str]:
    """Which optional fields apply to this query (base.md §12.3)."""
    attrs = query.expected_attributes
    fields = ["overall_relevance"]
    if attrs.mood:
        fields.append("mood_relevance")
    if attrs.instrument:
        fields.append("instrument_present")
    if query.expected_hard_constraints or attrs.vocals == "excluded":
        fields.append("constraint_satisfied")
    fields.append("basis")
    return fields


def pending_pairs(
    dataset: EvalDataset,
    *,
    seed: int = 42,
    only_queries: Collection[str] | None = None,
    only_tracks: Collection[int] | None = None,
) -> list[Pair]:
    """Unjudged pairs in a fixed pseudo-random order (avoids judging one query in a row)."""
    judged = {(j.query_id, j.fma_track_id) for j in dataset.judgments}
    pairs = [
        Pair(q, m)
        for q in dataset.queries
        for m in dataset.manifest
        if (q.query_id, m.fma_track_id) not in judged
        and (only_queries is None or q.query_id in only_queries)
        and (only_tracks is None or m.fma_track_id in only_tracks)
    ]
    return sorted(
        pairs,
        key=lambda p: hashlib.sha256(
            f"{seed}:{p.query.query_id}:{p.track.fma_track_id}".encode()
        ).hexdigest(),
    )


class AnswerError(ValueError):
    pass


def build_judgment(
    pair: Pair, answers: Mapping[str, str], *, judge: str, judged_at: datetime
) -> Judgment:
    """Validate the answers given for a pair; unasked optional fields stay empty."""
    asked = asked_fields(pair.query)
    missing = [f for f in asked if not answers.get(f, "").strip()]
    if missing:
        raise AnswerError(f"missing answers: {', '.join(missing)}")
    row: dict[str, object] = {
        "query_id": pair.query.query_id,
        "fma_track_id": pair.track.fma_track_id,
        "judge": judge,
        "judged_at": judged_at,
    }
    for field in asked:
        row[field] = answers[field].strip()
    try:
        return Judgment.model_validate(row)
    except ValidationError as exc:
        error = exc.errors(include_url=False)[0]
        raise AnswerError(f"{'.'.join(map(str, error['loc']))}: {error['msg']}") from exc


def append_judgment(path: Path, judgment: Judgment) -> None:
    """Append one row; writes the header if the file is new."""
    is_new = not path.is_file() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=JUDGMENT_COLUMNS, lineterminator="\n")
        if is_new:
            writer.writeheader()
        data = judgment.model_dump(mode="json")
        writer.writerow({k: "" if data.get(k) is None else data[k] for k in JUDGMENT_COLUMNS})
