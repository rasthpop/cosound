"""Per-task LLM switches at the composition root (ADR-0007). No test touches the network."""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from music_discovery.api.dependencies import llm_clients
from music_discovery.infrastructure.llm import OpenRouterLLM
from music_discovery.infrastructure.settings import Settings


def make(**overrides: Any) -> Settings:
    return Settings(_env_file=None, llm_provider="openrouter", **overrides)  # type: ignore[call-arg]


def client() -> OpenRouterLLM:
    return OpenRouterLLM(api_key=SecretStr("sk-test"), models=["vendor/model:free"])


def test_enabling_the_provider_does_not_enable_feedback_or_descriptions() -> None:
    llm = client()
    clients = llm_clients(make(), llm)
    assert clients.query is llm
    assert clients.feedback is None
    assert clients.descriptions is None


def test_each_task_has_its_own_switch() -> None:
    llm = client()
    clients = llm_clients(make(llm_query=False, llm_feedback=True, llm_descriptions=True), llm)
    assert clients.query is None
    assert clients.feedback is llm
    assert clients.descriptions is llm


def test_no_client_means_every_task_is_deterministic() -> None:
    clients = llm_clients(make(llm_feedback=True, llm_descriptions=True), None)
    assert (clients.query, clients.feedback, clients.descriptions) == (None, None, None)
