"""Shared base classes and field types for domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    """Immutable, strict domain model. Change values with `model_copy(update=...)`."""

    model_config = ConfigDict(frozen=True, extra="forbid")


def _strip_non_empty(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty")
    return stripped


def _web_url(value: str) -> str:
    if not value.startswith(("http://", "https://")) or len(value) < 12:
        raise ValueError("must be an absolute http(s) URL")
    return value


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value


NonEmptyStr = Annotated[str, AfterValidator(_strip_non_empty)]
WebUrl = Annotated[str, AfterValidator(_web_url)]
"""Absolute URL kept exactly as received from the source (never constructed by hand)."""
AwareDatetime = Annotated[datetime, AfterValidator(_aware)]
UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]
