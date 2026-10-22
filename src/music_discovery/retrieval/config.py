"""Retrieval configuration (config/retrieval.yaml).

Weights and thresholds are configuration, never constants in code (base.md §7.5). The shipped
values are starting points; P05.T06 calibrates them on the dev split only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

Strategy = Literal["minmax", "max_scale", "rank", "zscore_sigmoid", "calibrated"]
Signal = Literal["semantic", "metadata", "relationship"]


class _Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SignalWeights(_Config):
    semantic: float = Field(default=0.6, ge=0)
    metadata: float = Field(default=0.4, ge=0)
    relationship: float = Field(default=0.0, ge=0)

    def of(self, signal: Signal) -> float:
        return float(getattr(self, signal))


class CalibratedParams(_Config):
    """Logistic mapping 1 / (1 + exp(-(slope * x + intercept))), fitted on the dev split."""

    slope: float
    intercept: float


class NormalizationConfig(_Config):
    semantic: Strategy = "minmax"
    metadata: Strategy = "max_scale"
    relationship: Strategy = "max_scale"
    min_pool: int = Field(default=3, ge=2)
    """Smaller pools fall back to rank normalization."""
    calibrated: dict[Signal, CalibratedParams] = {}

    def strategy(self, signal: Signal) -> Strategy:
        return getattr(self, signal)  # type: ignore[no-any-return]


class ConstraintConfig(_Config):
    unknown: Literal["keep_flagged", "demote", "exclude"] = "keep_flagged"
    unknown_demotion: float = Field(default=0.5, gt=0, le=1)
    """Score multiplier per unknown constraint when `unknown == "demote"`."""


class DiversityConfig(_Config):
    scale: float = Field(default=0.6, ge=0, le=1)
    """MMR lambda = 1 - spec.diversity * scale."""
    duplicate_cosine: float = Field(default=0.9999, gt=0, le=1)
    """Audio this similar is the same recording (FMA double uploads); never shown twice."""


class PenaltyConfig(_Config):
    negative_reference: float = Field(default=0.3, ge=0, le=1)
    """Subtracted x max cosine to tracks marked LESS_LIKE_THIS."""
    negative_preference: float = Field(default=0.2, ge=0, le=1)
    """Subtracted when a negative-preference term is in the track's metadata."""


class RetrievalConfig(_Config):
    weights_version: str
    weights: SignalWeights = SignalWeights()
    normalization: NormalizationConfig = NormalizationConfig()
    constraints: ConstraintConfig = ConstraintConfig()
    diversity: DiversityConfig = DiversityConfig()
    penalties: PenaltyConfig = PenaltyConfig()
    coverage_penalty_gamma: float = Field(default=0.0, ge=0)
    """final *= (sum of available weights / sum of all weights) ** gamma; 0 disables it."""
    pool_size: int = Field(default=100, ge=1)
    semantic_top_k: int = Field(default=100, ge=1)
    metadata_top_k: int = Field(default=100, ge=1)

    @classmethod
    def load(cls, path: Path) -> RetrievalConfig:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
