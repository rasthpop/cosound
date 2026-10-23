"""Template descriptions and match reasons from TrackEvidence (base §8; grounded-explanations).

Evidence becomes a list of claims, each with one fixed sentence and a reason chip. The
description is at most two of those sentences: the strongest positive claim, then the most
important caveat (an unverified constraint, missing audio) or else the next positive claim.
Every sentence is checked by the claim validator before it is shown; a sentence that fails
is dropped. No evidence, no description (`None`) - nothing is padded. With an `LLMPhrasing`
the same claims may be rephrased; any rejected output keeps the template (`generator` says
which text is shown).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Literal

from music_discovery.descriptions.claim_validator import (
    CAVEATS,
    CitedSentence,
    Claim,
    ClaimKind,
    DescriptionConfig,
    validate,
)
from music_discovery.descriptions.evidence_builder import REFERENCE_PROMPT
from music_discovery.descriptions.llm_phrasing import LLMPhrasing
from music_discovery.domain.enums import ConstraintStatus, DataSource, MatchStrength
from music_discovery.domain.models import Track
from music_discovery.domain.schemas import (
    ConstraintAttribute,
    ConstraintOperator,
    ConstraintResult,
    Explanation,
    TagMatch,
    TrackEvidence,
)

log = logging.getLogger(__name__)
SOURCE_LABEL = {DataSource.FMA: "FMA", DataSource.DISCOGS: "Discogs"}
LEXICAL_FIELDS = {
    "title": ("Its title mentions", "Title"),
    "album": ("Its album title mentions", "Album"),
    "artist": ("The artist name matches", "Artist"),
}
_TAG_IN_EVIDENCE = re.compile(r"'([^']+)'")
POSITIVE_ORDER = (
    "semantic:strong",
    ClaimKind.CONSTRAINT_MET,
    ClaimKind.GENRE,
    ClaimKind.TAG,
    "semantic:partial",
    ClaimKind.LEXICAL,
    "semantic:weak",
)
CAVEAT_ORDER = (ClaimKind.CONSTRAINT_UNKNOWN, ClaimKind.SEMANTIC_UNAVAILABLE, ClaimKind.NO_AUDIO)


class DescriptionService:
    def __init__(self, config: DescriptionConfig, phrasing: LLMPhrasing | None = None) -> None:
        self._config = config
        self._phrasing = phrasing

    @property
    def config(self) -> DescriptionConfig:
        return self._config

    def claims(self, evidence: TrackEvidence, track: Track | None = None) -> list[Claim]:
        drafts: list[tuple[str, ClaimKind, str, str | None, str]] = []
        drafts += _semantic(evidence)
        drafts += _constraints_met(evidence.constraint_results, track)
        drafts += _genres(evidence.genre_matches)
        drafts += _metadata(evidence)
        drafts += _caveats(evidence)
        ordered = sorted(drafts, key=lambda d: _ORDER.index(d[0]))
        return [
            Claim(id=f"c{i}", kind=kind, text=text, reason=reason, evidence=ref)
            for i, (_, kind, text, reason, ref) in enumerate(ordered, start=1)
        ]

    def describe(self, evidence: TrackEvidence, track: Track | None = None) -> Explanation:
        claims = [c for c in self.claims(evidence, track) if self._valid(c, evidence)]
        positives = [c for c in claims if c.kind not in CAVEATS]
        caveats = [c for c in claims if c.kind in CAVEATS]
        chosen = positives[:1] + (caveats[:1] or positives[1:2])
        if not chosen:
            chosen = caveats[:2]
        chosen = chosen[: self._config.max_sentences]
        rest = [c for c in claims if c not in chosen]
        reasons = [c.reason for c in [*chosen, *rest] if c.reason is not None]
        text = " ".join(c.text for c in chosen) or None
        generator: Literal["template", "llm"] = "template"
        if self._phrasing is not None and chosen:
            required = [c.id for c in chosen if c.kind in CAVEATS]
            outcome = self._phrasing.phrase(claims, evidence, required=required)
            if outcome.text is not None:
                text, generator = outcome.text, "llm"
            else:
                log.info("llm phrasing rejected for %s: %s", evidence.track_id, outcome.reason)
        return Explanation(
            track_id=evidence.track_id,
            description=text,
            match_reasons=list(dict.fromkeys(reasons))[: self._config.max_reasons],
            generator=generator,
        )

    def _valid(self, claim: Claim, evidence: TrackEvidence) -> bool:
        result = validate([CitedSentence(claim.text, (claim.id,))], [claim], evidence, self._config)
        if not result.ok:
            log.warning("template claim %s dropped: %s", claim.evidence, result.violations)
        return result.ok


_ORDER: tuple[str, ...] = (*POSITIVE_ORDER, *CAVEAT_ORDER)
Draft = tuple[str, ClaimKind, str, str | None, str]
"""(order key, kind, sentence, reason chip, evidence reference)"""


def _d(kind: ClaimKind, text: str, reason: str | None, ref: str, order: str | None = None) -> Draft:
    return order or kind, kind, text, reason, ref


def _semantic(evidence: TrackEvidence) -> list[Draft]:
    s = evidence.semantic
    if s is None:
        return []
    # only expansion prompts are quoted: they never carry negations, while the request text
    # may ("... without vocals"), and quoting it would read as a claim CLAP cannot make
    targets = {"expansion": f'"{s.prompt.rstrip(".!?")}"', "reference": REFERENCE_PROMPT}
    target = targets.get(s.query_kind or "", "your request")
    texts = {
        MatchStrength.STRONG: (f"Its audio is a strong match for {target}.", "Strong audio match"),
        MatchStrength.PARTIAL: (
            "Its audio is a partial match for the requested sound.",
            "Partial audio match",
        ),
        MatchStrength.WEAK: (
            "Its audio is only a loose match for the request.",
            "Weak audio match",
        ),
    }
    text, reason = texts[s.strength]
    return [_d(ClaimKind.SEMANTIC, text, reason, "semantic", order=f"semantic:{s.strength}")]


def _label(source: DataSource) -> str:
    return SOURCE_LABEL.get(source, str(source))


def _genres(matches: Sequence[TagMatch]) -> list[Draft]:
    by_source: dict[DataSource, list[TagMatch]] = {}
    for m in matches:
        by_source.setdefault(m.source, []).append(m)
    drafts: list[Draft] = []
    for source, tags in by_source.items():
        listed = " and ".join(f'"{t.tag}"' for t in tags[:3])
        text = f"Listed under {listed} in {_label(source)}."
        reason = f"Tagged: {tags[0].tag}"
        drafts.append(_d(ClaimKind.GENRE, text, reason, "genre_matches"))
    return drafts


def _metadata(evidence: TrackEvidence) -> list[Draft]:
    drafts: list[Draft] = []
    tags = [m.term for m in evidence.metadata_matches if m.field == "tags"]
    if tags:
        source = next(m.source for m in evidence.metadata_matches if m.field == "tags")
        listed = " and ".join(f'"{t}"' for t in tags[:3])
        text = f"Its {_label(source)} tags include {listed}."
        drafts.append(_d(ClaimKind.TAG, text, f"Tag: {tags[0]}", "metadata_matches"))
    for m in evidence.metadata_matches:
        if m.field in LEXICAL_FIELDS:
            lead, chip = LEXICAL_FIELDS[m.field]
            text = f'{lead} "{m.term}".'
            drafts.append(_d(ClaimKind.LEXICAL, text, f"{chip}: {m.term}", "metadata_matches"))
        elif m.field == "year":
            text = f'Its release year falls in the "{m.term}".'
            drafts.append(_d(ClaimKind.LEXICAL, text, f"Era: {m.term}", "metadata_matches"))
    return drafts


def _constraints_met(results: Sequence[ConstraintResult], track: Track | None) -> list[Draft]:
    drafts: list[Draft] = []
    for i, r in enumerate(results):
        if r.status is not ConstraintStatus.SATISFIED:
            continue
        c, ref = r.constraint, f"constraint_results[{i}]"
        tag = next((t for e in r.evidence for t in _TAG_IN_EVIDENCE.findall(e)), None)
        source = _label(track.provenance.source) if track is not None else None
        if c.attribute is ConstraintAttribute.VOCALS and tag and source:
            text = f'Listed under "{tag}" in {source}, which meets your requirement.'
            drafts.append(_d(ClaimKind.CONSTRAINT_MET, text, f"Tagged: {tag}", ref))
        elif c.attribute is ConstraintAttribute.GENRE and c.operator is ConstraintOperator.REQUIRED:
            if tag and source:
                text = f'Listed under "{tag}" in {source}, as you required.'
                drafts.append(_d(ClaimKind.CONSTRAINT_MET, text, f"Tagged: {tag}", ref))
        elif c.attribute is ConstraintAttribute.GENRE and c.value:
            text = f'It is not tagged "{c.value}".'
            drafts.append(_d(ClaimKind.CONSTRAINT_MET, text, f"Not tagged: {c.value}", ref))
        elif c.attribute is ConstraintAttribute.ERA and track is not None and track.year:
            text = f"Released in {track.year}, within your requested years."
            drafts.append(_d(ClaimKind.CONSTRAINT_MET, text, f"Released {track.year}", ref))
        elif c.attribute is ConstraintAttribute.DURATION and track and track.duration_seconds:
            minutes, seconds = divmod(round(track.duration_seconds), 60)
            text = f"Runs {minutes}:{seconds:02d}, within your requested length."
            drafts.append(_d(ClaimKind.CONSTRAINT_MET, text, "Length fits", ref))
    return drafts


def _unknown_text(r: ConstraintResult) -> tuple[str, str]:
    c = r.constraint
    match c.attribute:
        case ConstraintAttribute.VOCALS:
            return "Vocal content could not be verified.", "Vocals unverified"
        case ConstraintAttribute.INSTRUMENT if c.operator is ConstraintOperator.EXCLUDED:
            return f'The absence of "{c.value}" could not be verified.', f"No {c.value}: unverified"
        case ConstraintAttribute.INSTRUMENT:
            return f'The presence of "{c.value}" could not be verified.', f"{c.value}: unverified"
        case ConstraintAttribute.TEMPO:
            return "Its tempo could not be verified.", "Tempo unverified"
        case ConstraintAttribute.ERA:
            return "Its release year is unknown.", "Year unknown"
        case ConstraintAttribute.DURATION:
            return "Its length is unknown.", "Length unknown"
        case ConstraintAttribute.GENRE:
            return "It has no genre tags to check your requirement against.", "Genre unverified"
    raise AssertionError(c.attribute)


def _caveats(evidence: TrackEvidence) -> list[Draft]:
    drafts: list[Draft] = []
    for i, r in enumerate(evidence.constraint_results):
        if r.status is ConstraintStatus.UNKNOWN:
            text, reason = _unknown_text(r)
            kind = ClaimKind.CONSTRAINT_UNKNOWN
            drafts.append(_d(kind, text, reason, f"constraint_results[{i}]"))
    if "semantic_unavailable" in evidence.uncertainty_flags:
        text = "Audio search was unavailable; matched on catalog metadata."
        kind = ClaimKind.SEMANTIC_UNAVAILABLE
        drafts.append((kind, kind, text, "Metadata only", "uncertainty_flags"))
    if "no_audio" in evidence.uncertainty_flags:
        text = "Audio analysis unavailable; matched on catalog metadata."
        drafts.append(_d(ClaimKind.NO_AUDIO, text, "No audio analysis", "uncertainty_flags"))
    return drafts
