"""LLM drafts for Agent A in tests."""

from __future__ import annotations

from music_discovery.agents.llm_query_interpreter import DraftPreference, SearchSpecificationDraft


def flute_draft() -> SearchSpecificationDraft:
    """What a well-behaved model answers for "calm flute melody"."""
    return SearchSpecificationDraft(
        preferences=[
            DraftPreference(category="mood", value="calm", weight=0.7, source_span="calm"),
            DraftPreference(category="instrument", value="flute", weight=1.0, source_span="flute"),
        ],
        negative_preferences=[],
        vocals="unspecified",
        hard_constraints=[],
        reference_track_ids=[],
        needs_clarification=False,
        clarification_question=None,
    )
