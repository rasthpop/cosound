"""Per-signal score normalization to [0, 1] (base.md §7.5).

Only present values are normalized; `None` (signal not available) stays `None`.
Pools that are too small or have no spread fall back to rank normalization, and the
fallback is reported so it shows up in the retrieval trace.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from music_discovery.retrieval.config import CalibratedParams, Strategy


@dataclass(frozen=True)
class Normalized:
    values: dict[str, float | None]
    strategy: Strategy
    fallback: str | None = None
    """Why the requested strategy was replaced, if it was."""


def _rank(present: Mapping[str, float]) -> dict[str, float]:
    """1.0 for the best, 0.0 for the worst; ties share their average position."""
    if len(present) == 1:
        return dict.fromkeys(present, 1.0)
    ordered = sorted(present.items(), key=lambda kv: -kv[1])
    positions: dict[float, list[int]] = {}
    for position, (_, value) in enumerate(ordered):
        positions.setdefault(value, []).append(position)
    n = len(ordered) - 1
    return {k: 1.0 - (sum(positions[v]) / len(positions[v])) / n for k, v in present.items()}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def normalize(
    scores: Mapping[str, float | None],
    strategy: Strategy,
    *,
    min_pool: int = 3,
    calibrated: CalibratedParams | None = None,
) -> Normalized:
    present = {k: float(v) for k, v in scores.items() if v is not None}
    out: dict[str, float | None] = dict.fromkeys(scores)
    if not present:
        return Normalized(out, strategy)

    if strategy == "calibrated":
        if calibrated is None:
            raise ValueError("calibrated normalization needs fitted parameters")
        out.update(
            {k: _sigmoid(calibrated.slope * v + calibrated.intercept) for k, v in present.items()}
        )
        return Normalized(out, strategy)

    if strategy == "max_scale":
        top = max(present.values())
        if top <= 0:
            # nothing matched anywhere in the pool: no evidence to rescale
            out.update(dict.fromkeys(present, 0.0))
            return Normalized(out, strategy)
        out.update({k: max(v, 0.0) / top for k, v in present.items()})
        return Normalized(out, strategy)

    if strategy == "rank":
        out.update(_rank(present))
        return Normalized(out, strategy)

    low, high = min(present.values()), max(present.values())
    if len(present) < min_pool or math.isclose(low, high):
        reason = "pool_too_small" if len(present) < min_pool else "no_spread"
        out.update(_rank(present))
        return Normalized(out, "rank", fallback=f"{strategy}->rank:{reason}")

    if strategy == "minmax":
        out.update({k: (v - low) / (high - low) for k, v in present.items()})
        return Normalized(out, strategy)

    mean = sum(present.values()) / len(present)
    std = math.sqrt(sum((v - mean) ** 2 for v in present.values()) / len(present))
    out.update({k: _sigmoid((v - mean) / std) for k, v in present.items()})
    return Normalized(out, strategy)
