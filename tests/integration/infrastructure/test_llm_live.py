"""One live OpenRouter call (run with --run-live; skipped without a configured model and key)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from music_discovery.infrastructure.llm import build_llm
from music_discovery.infrastructure.settings import get_settings


class Mood(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mood: str


@pytest.mark.live
def test_configured_model_answers_a_tiny_schema() -> None:
    llm = build_llm(get_settings())
    if llm is None:
        pytest.skip("LLM_PROVIDER, OPENROUTER_API_KEY and LLM_MODEL are not all set")
    result = llm.generate(
        task="query",
        system="Name the mood of the request in one lowercase word.",
        user="something chill",
        schema=Mood,
    )
    assert result.error_code is None, result.error_code
    assert result.parsed is not None
    assert result.model_id
