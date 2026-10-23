from __future__ import annotations

import json
import logging

import pytest

from music_discovery.descriptions.claim_validator import DescriptionConfig
from music_discovery.descriptions.description_service import DescriptionService
from music_discovery.descriptions.evidence_builder import EvidenceBuilder, SemanticSignal
from music_discovery.descriptions.llm_phrasing import DraftSentence, LLMPhrasing, PhrasingDraft
from music_discovery.domain.enums import ConstraintStatus, DataSource, RetrievalSource
from music_discovery.domain.models import Provenance, Track
from music_discovery.domain.schemas import (
    ConstraintAttribute,
    ConstraintOperator,
    ConstraintResult,
    FieldMatch,
    HardConstraint,
    RankedCandidate,
    ScoreBreakdown,
    TrackEvidence,
)
from tests.fakes import FakeStructuredLLM

CONFIG = DescriptionConfig.load()
MODEL = "vendor/model:free"
TRACK = Track(
    id="trk_1", provenance=Provenance(source=DataSource.FMA), title="Song", genres=["Chill-out"]
)
UNKNOWN_VOCALS = ConstraintResult(
    constraint=HardConstraint(
        attribute=ConstraintAttribute.VOCALS, operator=ConstraintOperator.EXCLUDED
    ),
    status=ConstraintStatus.UNKNOWN,
)
HIT = SemanticSignal(
    prompt="chill music with a flute", raw_cosine=0.3, rank=1, model_id="clap", kind="expansion"
)


def evidence(results: list[ConstraintResult] | None = None) -> TrackEvidence:
    candidate = RankedCandidate(
        track_id="trk_1",
        rank=1,
        score=ScoreBreakdown(semantic=0.95, metadata=0.6, final=0.9),
        retrieval_sources=[RetrievalSource.SEMANTIC, RetrievalSource.METADATA],
        constraint_results=results or [],
    )
    genre = FieldMatch(field="genres", term="chill", source=DataSource.FMA, kind="tag")
    return EvidenceBuilder(CONFIG.semantic_bands).build(
        candidate, TRACK, matched_fields=[genre], semantic=HIT
    )


def sentences(*items: tuple[str, list[str]]) -> PhrasingDraft:
    return PhrasingDraft(sentences=[DraftSentence(text=t, claim_ids=ids) for t, ids in items])


def service(*responses: PhrasingDraft | str) -> tuple[DescriptionService, FakeStructuredLLM]:
    llm = FakeStructuredLLM(list(responses), model_id=MODEL)
    return DescriptionService(CONFIG, LLMPhrasing(llm, CONFIG)), llm


GOOD = sentences(
    ('Its audio closely matches "chill music with a flute".', ["c1"]),
    ('It is listed under "Chill-out" in FMA.', ["c2"]),
)


def test_cited_output_is_accepted() -> None:
    svc, _ = service(GOOD)
    explanation = svc.describe(evidence(), TRACK)
    assert explanation.generator == "llm"
    assert explanation.description == (
        'Its audio closely matches "chill music with a flute". '
        'It is listed under "Chill-out" in FMA.'
    )
    assert explanation.match_reasons == ["Strong audio match", "Tagged: Chill-out"]


def test_llm_sees_only_the_claim_list() -> None:
    svc, llm = service(GOOD)
    svc.describe(evidence(), TRACK)
    [call] = llm.calls
    assert call.task == "descriptions"
    payload = json.loads(call.user)
    assert [c["id"] for c in payload] == ["c1", "c2"]
    assert set(payload[0]) == {"id", "claim"}
    assert "trk_1" not in call.user


@pytest.mark.parametrize(
    ("draft", "reason"),
    [
        (sentences(("It is a lovely chill tune.", [])), "cites no claim"),
        (sentences(("Its audio closely matches the request.", ["c7"])), "unknown claims"),
        (sentences(("It contains a gentle flute.", ["c1"])), "forbidden wording"),
        (sentences(("Its audio is a 92% match.", ["c1"])), "percentage"),
        (sentences(('It matches "jazz with saxophone".', ["c1"])), "quotes"),
        (sentences(("A flute leads the melody.", ["c1"])), "names instruments"),
        (
            sentences(("One.", ["c1"]), ("Two.", ["c1"]), ("Three.", ["c2"])),
            "3 sentences",
        ),
        (sentences(), "empty_output"),
        ("invalid_output", "llm_invalid_output"),
        ("rate_limited", "llm_rate_limited"),
    ],
)
def test_rejected_output_falls_back_to_template_with_reason(
    draft: PhrasingDraft | str, reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    svc, _ = service(draft)
    template = DescriptionService(CONFIG).describe(evidence(), TRACK)
    with caplog.at_level(logging.INFO, logger="music_discovery.descriptions.description_service"):
        explanation = svc.describe(evidence(), TRACK)
    assert explanation == template
    assert explanation.generator == "template"
    assert reason in caplog.text


def test_dropping_an_unverified_constraint_caveat_is_rejected(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ev = evidence([UNKNOWN_VOCALS])
    claims = DescriptionService(CONFIG).claims(ev, TRACK)
    caveat = next(c for c in claims if c.text == "Vocal content could not be verified.")
    svc, _ = service(sentences(('Its audio closely matches "chill music with a flute".', ["c1"])))
    with caplog.at_level(logging.INFO):
        explanation = svc.describe(ev, TRACK)
    assert explanation.generator == "template"
    assert "dropped caveat" in caplog.text
    assert explanation.description is not None
    assert caveat.text in explanation.description


def test_disabled_by_default() -> None:
    assert DescriptionService(CONFIG).describe(evidence(), TRACK).generator == "template"


def test_no_evidence_does_not_call_the_llm() -> None:
    svc, llm = service(GOOD)
    explanation = svc.describe(TrackEvidence(track_id="trk_1"))
    assert explanation.description is None
    assert llm.calls == []
