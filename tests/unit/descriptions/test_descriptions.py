from __future__ import annotations

import pytest

from music_discovery.descriptions.claim_validator import (
    CitedSentence,
    Claim,
    ClaimKind,
    DescriptionConfig,
    ScoreBandConfig,
    SignalBands,
    split_sentences,
    validate,
)
from music_discovery.descriptions.description_service import DescriptionService
from music_discovery.descriptions.evidence_builder import (
    EvidenceBuilder,
    SemanticSignal,
    signal_strength,
    strength,
)
from music_discovery.domain.enums import (
    ConstraintStatus,
    DataSource,
    MatchStrength,
    RetrievalSource,
)
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

CONFIG = DescriptionConfig.load()
BANDS = CONFIG.semantic_bands
BUILDER = EvidenceBuilder(BANDS)
SERVICE = DescriptionService(CONFIG)
MODEL = "laion/clap@abc"
FMA = Provenance(source=DataSource.FMA)
VOCALS_EXCLUDED = HardConstraint(
    attribute=ConstraintAttribute.VOCALS, operator=ConstraintOperator.EXCLUDED
)
NO_DRUMS = HardConstraint(
    attribute=ConstraintAttribute.INSTRUMENT, operator=ConstraintOperator.EXCLUDED, value="drums"
)


def track(**overrides: object) -> Track:
    data: dict[str, object] = {
        "id": "trk_1",
        "provenance": FMA,
        "title": "Morning Flute",
        "genres": ["Ambient Electronic", "Chill-out"],
        "year": 2009,
        "duration_seconds": 165.0,
    }
    return Track.model_validate(data | overrides)


def candidate(
    semantic: float | None = 0.95,
    metadata: float | None = 0.8,
    results: list[ConstraintResult] | None = None,
) -> RankedCandidate:
    sources = [RetrievalSource.SEMANTIC] if semantic is not None else []
    sources += [RetrievalSource.METADATA] if metadata is not None else []
    return RankedCandidate(
        track_id="trk_1",
        rank=1,
        score=ScoreBreakdown(semantic=semantic, metadata=metadata, final=0.9),
        retrieval_sources=sources,
        constraint_results=results or [],
    )


def genre(term: str) -> FieldMatch:
    return FieldMatch(field="genres", term=term, source=DataSource.FMA, kind="tag")


def title(term: str) -> FieldMatch:
    return FieldMatch(field="title", term=term, source=DataSource.FMA, kind="lexical")


HIT = SemanticSignal(prompt="chill music with a flute", raw_cosine=0.31, rank=1, model_id=MODEL)


def describe(**kwargs: object) -> tuple[TrackEvidence, str | None, list[str]]:
    cand = kwargs.pop("candidate", candidate())
    trk = kwargs.pop("track", track())
    evidence = BUILDER.build(cand, trk, **kwargs)  # type: ignore[arg-type]
    explanation = SERVICE.describe(evidence, trk)  # type: ignore[arg-type]
    return evidence, explanation.description, explanation.match_reasons


# --- evidence and strength bands --------------------------------------------------------


def test_strength_bands() -> None:
    assert strength(1, BANDS.tau_strong, BANDS) is MatchStrength.STRONG
    assert strength(BANDS.strong_max_rank + 1, 1.0, BANDS) is MatchStrength.PARTIAL
    assert strength(1, BANDS.tau_partial, BANDS) is MatchStrength.PARTIAL
    assert strength(1, BANDS.tau_partial - 0.01, BANDS) is MatchStrength.WEAK
    assert strength(1, None, BANDS) is MatchStrength.WEAK


def test_signal_bands_are_thresholds_and_null_without_a_signal() -> None:
    bands = SignalBands(tau_strong=0.8, tau_partial=0.3)
    assert signal_strength(0.8, bands) is MatchStrength.STRONG
    assert signal_strength(0.3, bands) is MatchStrength.PARTIAL
    assert signal_strength(0.0, bands) is MatchStrength.WEAK  # evaluated, nothing matched
    assert signal_strength(None, bands) is None  # missing is not weak
    assert signal_strength(0.9, None) is None  # no calibrated bands
    with pytest.raises(ValueError, match="tau_partial"):
        SignalBands(tau_strong=0.3, tau_partial=0.8)


def test_evidence_records_a_band_per_signal() -> None:
    builder = EvidenceBuilder(BANDS, CONFIG.score_bands)
    strong = builder.build(candidate(semantic=0.95, metadata=0.0), track(), semantic=HIT)
    assert strong.score_bands.semantic is MatchStrength.STRONG
    assert strong.score_bands.metadata is MatchStrength.WEAK
    assert strong.score_bands.relationship is None
    no_audio = builder.build(candidate(semantic=None, metadata=0.85), track())
    assert no_audio.score_bands.semantic is None
    assert no_audio.score_bands.metadata is MatchStrength.STRONG
    # without score-band config only the semantic band is set
    plain = EvidenceBuilder(BANDS).build(candidate(metadata=0.85), track(), semantic=HIT)
    assert plain.score_bands.semantic is MatchStrength.STRONG
    assert plain.score_bands.metadata is None


def test_relationship_has_no_bands_while_the_signal_is_off() -> None:
    assert CONFIG.score_bands.relationship is None
    builder = EvidenceBuilder(
        BANDS, ScoreBandConfig(relationship=SignalBands(tau_strong=0.9, tau_partial=0.5))
    )
    cand = RankedCandidate(
        track_id="trk_1",
        rank=1,
        score=ScoreBreakdown(relationship=0.6, final=0.6),
        retrieval_sources=[RetrievalSource.RELATIONSHIP],
    )
    assert builder.build(cand, track()).score_bands.relationship is MatchStrength.PARTIAL


def test_evidence_keeps_raw_cosine_and_matched_tags_as_cataloged() -> None:
    evidence, _, _ = describe(matched_fields=[genre("chill"), title("flute")], semantic=HIT)
    assert evidence.semantic is not None
    assert evidence.semantic.raw_cosine == 0.31
    assert evidence.semantic.normalized == 0.95
    assert evidence.semantic.strength is MatchStrength.STRONG
    assert [t.tag for t in evidence.genre_matches] == ["Chill-out"]
    assert [m.field for m in evidence.metadata_matches] == ["title"]
    assert evidence.uncertainty_flags == []


def test_missing_semantic_score_is_flagged_not_zero() -> None:
    evidence, _, _ = describe(candidate=candidate(semantic=None), matched_fields=[genre("chill")])
    assert evidence.semantic is None
    assert evidence.uncertainty_flags == ["no_audio"]


def test_degraded_semantic_is_flagged_as_unavailable() -> None:
    evidence, _, _ = describe(
        candidate=candidate(semantic=None), degraded=["semantic_unavailable:model_missing"]
    )
    assert evidence.uncertainty_flags == ["semantic_unavailable"]


# --- golden template outputs ------------------------------------------------------------


def test_golden_strong_audio_and_tag() -> None:
    _, text, reasons = describe(matched_fields=[genre("chill")], semantic=HIT)
    assert text == (
        'Its audio is a strong match for "chill music with a flute". '
        'Listed under "Chill-out" in FMA.'
    )
    assert reasons == ["Strong audio match", "Tagged: Chill-out"]


def test_golden_partial_audio_with_unverified_vocals() -> None:
    unknown = ConstraintResult(constraint=VOCALS_EXCLUDED, status=ConstraintStatus.UNKNOWN)
    hit = SemanticSignal(prompt="calm acoustic music", raw_cosine=0.2, rank=5, model_id=MODEL)
    _, text, reasons = describe(
        candidate=candidate(semantic=0.7, results=[unknown]), semantic=hit, matched_fields=[]
    )
    assert text == (
        "Its audio is a partial match for the requested sound. Vocal content could not be verified."
    )
    assert reasons == ["Partial audio match", "Vocals unverified"]


def test_golden_instrumental_constraint_met() -> None:
    met = ConstraintResult(
        constraint=VOCALS_EXCLUDED,
        status=ConstraintStatus.SATISFIED,
        evidence=["genre tag 'Instrumental' (fma)"],
    )
    trk = track(genres=["Instrumental"])
    _, text, _ = describe(candidate=candidate(semantic=0.2, results=[met]), track=trk, semantic=HIT)
    assert text == (
        'Listed under "Instrumental" in FMA, which meets your requirement. '
        "Its audio is only a loose match for the request."
    )


def test_golden_no_audio_track() -> None:
    _, text, reasons = describe(
        candidate=candidate(semantic=None), matched_fields=[title("flute")], semantic=None
    )
    assert text == (
        'Its title mentions "flute". Audio analysis unavailable; matched on catalog metadata.'
    )
    assert reasons == ["Title: flute", "No audio analysis"]


def test_golden_unknown_instrument_constraint() -> None:
    unknown = ConstraintResult(constraint=NO_DRUMS, status=ConstraintStatus.UNKNOWN)
    _, text, _ = describe(candidate=candidate(results=[unknown]), semantic=HIT)
    assert text == (
        'Its audio is a strong match for "chill music with a flute". '
        'The absence of "drums" could not be verified.'
    )


def test_golden_range_constraints_state_catalog_values() -> None:
    era = HardConstraint(
        attribute=ConstraintAttribute.ERA, operator=ConstraintOperator.RANGE, range=(2000, 2010)
    )
    met = ConstraintResult(
        constraint=era, status=ConstraintStatus.SATISFIED, evidence=["year 2009 (fma)"]
    )
    _, text, _ = describe(candidate=candidate(semantic=None, results=[met]))
    assert text == (
        "Released in 2009, within your requested years. "
        "Audio analysis unavailable; matched on catalog metadata."
    )


def test_reference_track_query_is_not_quoted() -> None:
    hit = SemanticSignal(prompt=None, raw_cosine=0.8, rank=1, model_id=MODEL, kind="reference")
    _, text, _ = describe(semantic=hit)
    assert text == "Its audio is a strong match for a track you liked."


def test_request_text_is_never_quoted_as_an_audio_match() -> None:
    query = "Calm acoustic music without vocals."
    hit = SemanticSignal(prompt=query, raw_cosine=0.3, rank=1, model_id=MODEL, kind="original")
    evidence, text, _ = describe(semantic=hit)
    assert text == "Its audio is a strong match for your request."
    assert evidence.semantic is not None
    assert evidence.semantic.prompt == query, "the evidence keeps the text that matched"


def test_no_evidence_gives_no_description() -> None:
    evidence = TrackEvidence(track_id="trk_1")
    explanation = SERVICE.describe(evidence)
    assert explanation.description is None
    assert explanation.match_reasons == []


# --- every sentence maps to evidence ----------------------------------------------------


CASES = [
    {"matched_fields": [genre("chill"), title("flute")], "semantic": HIT},
    {"candidate": candidate(semantic=None), "matched_fields": [title("flute")]},
    {
        "candidate": candidate(
            results=[ConstraintResult(constraint=NO_DRUMS, status=ConstraintStatus.UNKNOWN)]
        ),
        "semantic": HIT,
    },
]


@pytest.mark.parametrize("case", CASES)
def test_every_template_sentence_is_a_validated_claim(case: dict[str, object]) -> None:
    evidence, text, _ = describe(**case)
    assert text is not None
    claims = SERVICE.claims(evidence, track())
    by_text = {c.text: c for c in claims}
    sentences = split_sentences(text)
    assert all(s in by_text for s in sentences), "each sentence is one claim's template"
    cited = [CitedSentence(s, (by_text[s].id,)) for s in sentences]
    assert validate(cited, claims, evidence, CONFIG).ok
    for claim in claims:
        assert claim.evidence.split("[")[0] in TrackEvidence.model_fields


def test_no_audio_track_never_gets_sound_descriptors() -> None:
    evidence, text, _ = describe(
        candidate=candidate(semantic=None), matched_fields=[genre("chill"), title("flute")]
    )
    assert text is not None
    claims = SERVICE.claims(evidence, track())
    assert not any(c.kind is ClaimKind.SEMANTIC for c in claims)
    words = set(text.casefold().replace('"', " ").replace(".", " ").split())
    quoted = {"chill", "out", "flute"}
    assert not (words - quoted) & CONFIG.sound_descriptors


# --- forbidden phrasing -----------------------------------------------------------------


@pytest.fixture
def strong() -> tuple[TrackEvidence, list[Claim]]:
    evidence = BUILDER.build(candidate(), track(), matched_fields=[genre("chill")], semantic=HIT)
    return evidence, SERVICE.claims(evidence, track())


@pytest.mark.parametrize(
    ("text", "violation"),
    [
        ("This track contains a flute.", "forbidden wording"),
        ("It features a lovely flute.", "forbidden wording"),
        ("Its audio is a 87% match.", "percentage"),
        ("A flute plays throughout.", "names instruments"),
        ("It is chill and mellow.", "describes the sound"),
        ('Its audio is a strong match for "jazz with a saxophone".', "quotes"),
        ("Its audio scored 0.31 against the prompt.", "states 0.31"),
        ("It is probably what you want.", "forbidden wording"),
    ],
)
def test_forbidden_phrasing_is_rejected(
    strong: tuple[TrackEvidence, list[Claim]], text: str, violation: str
) -> None:
    evidence, claims = strong
    result = validate([CitedSentence(text, ("c1",))], claims, evidence, CONFIG)
    assert not result.ok
    assert any(violation in v for v in result.violations), result.violations


def test_uncited_and_too_many_sentences_are_rejected(
    strong: tuple[TrackEvidence, list[Claim]],
) -> None:
    evidence, claims = strong
    ok = claims[0].text
    result = validate(
        [CitedSentence(ok, ()), CitedSentence(ok, ("c9",)), CitedSentence(ok, ("c1",))],
        claims,
        evidence,
        CONFIG,
    )
    assert "3 sentences (max 2)" in result.violations
    assert "sentence 1 cites no claim" in result.violations
    assert any("unknown claims" in v for v in result.violations)


def test_semantic_claim_needs_audio_evidence(strong: tuple[TrackEvidence, list[Claim]]) -> None:
    _, claims = strong
    no_audio = TrackEvidence(track_id="trk_1", uncertainty_flags=["no_audio"])
    result = validate([CitedSentence(claims[0].text, ("c1",))], claims, no_audio, CONFIG)
    assert not result.ok
    assert any("audio match the track does not have" in v for v in result.violations)


def test_config_is_versioned() -> None:
    assert CONFIG.version.startswith("d2")
    assert 0 < BANDS.tau_partial < BANDS.tau_strong <= 1
