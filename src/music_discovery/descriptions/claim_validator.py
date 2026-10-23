"""What may be said about a track, and the check that a text says nothing more (base §8, §20).

A `Claim` is one evidence-backed statement with a fixed template sentence and a short reason
chip. A text is valid when every sentence cites at least one claim and, outside quotes, uses
no forbidden word (detection, presence, certainty, probability), no number the cited claims
do not state, no instrument noun, and no sound descriptor; quoted spans ("chill music with a
flute") must be copied from a cited claim. Only semantic claims quote a prompt, and they exist
only with audio evidence, so a track without audio cannot be described by its sound.

The validator is a pure function, shared by the description service, the optional LLM
phrasing, the evaluation and the evidence auditor.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from music_discovery.domain.schemas import TrackEvidence

DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "config" / "descriptions.yaml"
_QUOTED = re.compile(r'"([^"]+)"')
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z]+")
_NUMBER = re.compile(r"\d+(?:[.:]\d+)?")


class ClaimKind(StrEnum):
    SEMANTIC = "semantic"
    GENRE = "genre"
    TAG = "tag"
    LEXICAL = "lexical"
    CONSTRAINT_MET = "constraint_met"
    CONSTRAINT_UNKNOWN = "constraint_unknown"
    NO_AUDIO = "no_audio"
    SEMANTIC_UNAVAILABLE = "semantic_unavailable"
    RETRIEVAL = "retrieval"


CAVEATS = frozenset(
    {ClaimKind.CONSTRAINT_UNKNOWN, ClaimKind.NO_AUDIO, ClaimKind.SEMANTIC_UNAVAILABLE}
)


@dataclass(frozen=True)
class Claim:
    id: str
    kind: ClaimKind
    text: str
    """The template sentence; also what the optional LLM may rephrase."""
    reason: str | None
    """Short chip for `match_reasons`; None when the claim has no chip."""
    evidence: str
    """Which `TrackEvidence` item backs the claim (e.g. "semantic", "genre_matches[0]")."""


@dataclass(frozen=True)
class CitedSentence:
    text: str
    claim_ids: tuple[str, ...]


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    violations: list[str] = field(default_factory=list)


class SemanticBands(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    strong_max_rank: int = Field(default=3, ge=1)
    tau_strong: float = Field(ge=0.0, le=1.0)
    tau_partial: float = Field(ge=0.0, le=1.0)


class DescriptionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: str
    semantic_bands: SemanticBands
    max_sentences: int = Field(default=2, ge=1)
    max_reasons: int = Field(default=4, ge=1)
    forbidden: frozenset[str]
    instrument_nouns: frozenset[str]
    sound_descriptors: frozenset[str]

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG) -> DescriptionConfig:
        return cls.model_validate(yaml.safe_load(path.read_text()))


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text.strip()) if s.strip()]


def validate(
    sentences: Sequence[CitedSentence],
    claims: Sequence[Claim],
    evidence: TrackEvidence,
    config: DescriptionConfig,
) -> ValidationResult:
    by_id = {c.id: c for c in claims}
    violations: list[str] = []
    if len(sentences) > config.max_sentences:
        violations.append(f"{len(sentences)} sentences (max {config.max_sentences})")
    for i, sentence in enumerate(sentences, start=1):
        cited = [by_id[c] for c in sentence.claim_ids if c in by_id]
        if unknown := [c for c in sentence.claim_ids if c not in by_id]:
            violations.append(f"sentence {i} cites unknown claims {unknown}")
        if not cited:
            violations.append(f"sentence {i} cites no claim")
            continue
        if evidence.semantic is None and any(c.kind is ClaimKind.SEMANTIC for c in cited):
            violations.append(f"sentence {i} cites an audio match the track does not have")
        violations += _check_sentence(i, sentence.text, cited, config)
    return ValidationResult(ok=not violations, violations=violations)


def _check_sentence(
    i: int, text: str, cited: Sequence[Claim], config: DescriptionConfig
) -> list[str]:
    violations: list[str] = []
    cited_text = " ".join(c.text for c in cited).casefold()
    cited_quotes = {q.casefold() for c in cited for q in _QUOTED.findall(c.text)}
    for quote in _QUOTED.findall(text):
        if quote.casefold() not in cited_quotes:
            violations.append(f"sentence {i} quotes {quote!r}, which no cited claim states")
    bare = _QUOTED.sub(" ", text).casefold()
    words = set(_WORD.findall(bare))
    if "%" in bare:
        violations.append(f"sentence {i} uses a percentage")
    if hits := sorted(words & config.forbidden):
        violations.append(f"sentence {i} uses forbidden wording {hits}")
    if hits := sorted(words & config.instrument_nouns):
        violations.append(f"sentence {i} names instruments outside a quoted claim {hits}")
    if hits := sorted(words & config.sound_descriptors):
        violations.append(f"sentence {i} describes the sound outside a quoted claim {hits}")
    for number in _NUMBER.findall(bare):
        if number not in cited_text:
            violations.append(f"sentence {i} states {number}, which no cited claim does")
    return violations
