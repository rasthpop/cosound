from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.agent_c_feedback import FeedbackAgent
from music_discovery.agents.feedback_text import FeedbackTextNormalizer
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.agents.llm_query_interpreter import (
    DraftPreference,
    LLMQueryInterpreter,
    SearchSpecificationDraft,
)
from music_discovery.descriptions.claim_validator import DescriptionConfig
from music_discovery.descriptions.description_service import DescriptionService
from music_discovery.descriptions.evidence_builder import EvidenceBuilder
from music_discovery.domain.schemas import SearchSpecification
from music_discovery.evaluation import agent_eval
from music_discovery.evaluation.agent_eval import FeedbackCase, Score
from music_discovery.evaluation.datasets import load_dataset
from tests.fakes import FakeStructuredLLM, InMemoryTrackRepository

REAL = Path(__file__).parents[3] / "data" / "evaluation"
DATASET = load_dataset(REAL)
LEXICON = load_lexicon()
AGENT = QueryAgent(LEXICON)
CORPUS = [m.track_id for m in DATASET.manifest]


def fake_retrieve(spec: SearchSpecification) -> list[str]:
    """Deterministic order per query; honours exclusions, liked and disliked tracks."""
    order = sorted(
        (t for t in CORPUS if t not in spec.excluded_track_ids),
        key=lambda t: hashlib.sha256(f"{spec.original_query}:{t}".encode()).hexdigest(),
    )
    liked = [t for t in order if t in spec.reference_track_ids]
    disliked = [t for t in order if t in spec.negative_reference_track_ids]
    rest = [t for t in order if t not in liked and t not in disliked]
    return liked + rest + disliked


def feedback_agent() -> FeedbackAgent:
    config = DescriptionConfig.load()
    return FeedbackAgent(
        LEXICON,
        InMemoryTrackRepository(),
        EvidenceBuilder(config.semantic_bands),
        DescriptionService(config),
    )


def run_c(cases: list[FeedbackCase]) -> list[agent_eval.AgentCRow]:
    return agent_eval.evaluate_agent_c(
        cases,
        DATASET,
        query_agent=AGENT,
        feedback_agent=feedback_agent(),
        retrieve=fake_retrieve,
        normalizer=FeedbackTextNormalizer(LEXICON),
    )


# --- Agent A ----------------------------------------------------------------------------


def test_score_arithmetic() -> None:
    s = Score(tp=3, fp=1, fn=2)
    assert s.precision == pytest.approx(0.75)
    assert s.recall == pytest.approx(0.6)
    assert s.f1 == pytest.approx(2 * 0.75 * 0.6 / 1.35)
    assert Score().precision is None
    assert Score().f1 is None
    assert Score(tp=0, fp=1, fn=1).f1 == 0.0


def test_deterministic_agent_a_on_all_queries() -> None:
    rows = agent_eval.evaluate_agent_a(DATASET.queries, AGENT)
    metrics = agent_eval.agent_a_metrics(rows, llm_enabled=False)
    assert metrics["n_queries"] == 20
    assert metrics["micro"]["f1"] == 1.0
    assert metrics["hard_constraint_accuracy"] == 1.0
    assert metrics["vocals_accuracy"] == 1.0
    assert metrics["validity_rate"] == 1.0
    assert metrics["llm_acceptance_rate"] is None
    assert metrics["per_category"]["era"]["support"] >= 0
    assert all(r["disagreements"] == "" for r in agent_eval.agent_a_csv_rows(rows))


def test_agent_a_disagreements_and_llm_acceptance_are_reported() -> None:
    chill_only = SearchSpecificationDraft(
        preferences=[DraftPreference(category="mood", value="chill", weight=0.7, source_span="x")],
        negative_preferences=[],
        vocals="unspecified",
        hard_constraints=[],
        reference_track_ids=[],
        needs_clarification=False,
        clarification_question=None,
    )
    llm = FakeStructuredLLM([chill_only, "rate_limited"])
    agent = QueryAgent(LEXICON, LLMQueryInterpreter(llm, LEXICON))
    queries = [DATASET.query("q01"), DATASET.query("q11")]
    rows = agent_eval.evaluate_agent_a(queries, agent)
    metrics = agent_eval.agent_a_metrics(rows, llm_enabled=True)
    assert metrics["per_category"]["instrument"]["recall"] == 0.5, "flute missed on q01 only"
    assert metrics["llm_acceptance_rate"] == 0.5
    csv = agent_eval.agent_a_csv_rows(rows)
    assert "instrument: expected ['flute'] got []" in csv[0]["disagreements"]
    assert csv[0]["interpreter"] == "llm"
    assert csv[1]["llm_fallback_reason"] == "llm_rate_limited"


# --- Agent C ----------------------------------------------------------------------------


def test_committed_cases_load_and_reference_known_queries() -> None:
    cases = agent_eval.load_cases(REAL)
    assert len(cases) >= 10
    ids = {q.query_id for q in DATASET.queries}
    assert all(c.query_id in ids for c in cases)
    assert {c.case_id for c in cases} == {f"c{i:02d}" for i in range(1, len(cases) + 1)}


def test_all_committed_cases_pass_on_a_fake_retriever() -> None:
    rows = run_c(agent_eval.load_cases(REAL))
    failures = {r.case_id: r.failures for r in rows if r.failures}
    assert failures == {}
    metrics = agent_eval.agent_c_metrics(rows)
    assert metrics["constraint_preservation"] == 1.0
    assert metrics["spec_delta_accuracy"] == 1.0
    assert metrics["ranking_direction_accuracy"] == 1.0
    assert metrics["n_ranking_cases"] >= 4


def test_wrong_expectations_are_reported_as_failures() -> None:
    case = FeedbackCase(
        case_id="x1",
        query_id="q01",
        events=[{"event_type": "NOT_RELEVANT", "track": "rank:1"}],
        expected={"references": ["rank:1"], "preferences_added": {"genre": ["jazz"]}},
        ranking={"track": "rank:1", "direction": "up"},
    )
    [row] = run_c([case])
    assert not row.delta_ok
    assert row.preserved
    assert row.ranking_ok is False
    assert "rank:1 not in reference_track_ids" in row.failures
    assert "genre 'jazz' not added" in row.failures
    assert "rank:1 went gone, expected up" in row.failures
    assert agent_eval.agent_c_metrics([row])["failed_cases"] == ["x1"]


def test_rejected_feedback_counts_as_expected() -> None:
    case = FeedbackCase(
        case_id="x2",
        query_id="q06",
        events=[{"event_type": "MORE_OF_ATTRIBUTE", "attribute": "vocals"}],
        expected={"accepted": False, "vocals": "excluded"},
    )
    [row] = run_c([case])
    assert row.failures == []
    assert not row.accepted
    assert row.notes_ok


# --- report section ---------------------------------------------------------------------


def test_components_markdown() -> None:
    a = agent_eval.agent_a_metrics(
        agent_eval.evaluate_agent_a(DATASET.queries[:3], AGENT), llm_enabled=False
    )
    c = agent_eval.agent_c_metrics(run_c(agent_eval.load_cases(REAL)[:2]))
    text = "\n".join(agent_eval.components_markdown(a, c))
    assert "### Agent A (n = 3 queries)" in text
    assert "| mood |" in text
    assert "### Agent C (n = 2 feedback cases)" in text
    assert "constraint preservation 1.000" in text
    assert "does not measure how it generalizes" in text
