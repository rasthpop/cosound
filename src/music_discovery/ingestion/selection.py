"""Bounded, versioned Discogs import selection (config/discogs_selection.yaml)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

SeedKind = Literal["release", "artist", "label", "style", "genre"]


class Seed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: SeedKind
    id: int | None = Field(default=None, gt=0)
    value: str | None = None
    max_items: int = Field(default=25, ge=1, le=500)

    @model_validator(mode="after")
    def _id_or_value(self) -> Self:
        if self.kind in ("release", "artist", "label") and self.id is None:
            raise ValueError(f"{self.kind} seeds need an id")
        if self.kind in ("style", "genre") and not (self.value and self.value.strip()):
            raise ValueError(f"{self.kind} seeds need a value")
        return self

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.id if self.id is not None else self.value}:{self.max_items}"


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    selection_version: int = Field(ge=1)
    max_releases: int = Field(ge=1, le=5000)
    seeds: list[Seed] = Field(min_length=1)

    @property
    def selection_hash(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    @classmethod
    def load(cls, path: Path) -> Selection:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
