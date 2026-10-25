from __future__ import annotations

from music_discovery.application.capabilities import Capabilities, turn_warnings
from music_discovery.domain.enums import CapabilityStatus, InterpreterStatus
from tests.support.world import World


def test_health_capabilities_per_mode() -> None:
    full = World().capabilities.current()
    assert (full.semantic, full.llm_interpreter, full.map) == (
        CapabilityStatus.AVAILABLE,
        InterpreterStatus.DISABLED,
        CapabilityStatus.AVAILABLE,
    )
    down = World(semantic=False, projection_available=False).capabilities.current()
    assert down.semantic is CapabilityStatus.UNAVAILABLE
    assert down.semantic_reason == "clap_checkpoint_missing"
    assert down.map is CapabilityStatus.UNAVAILABLE
    assert down.map_reason == "projection_unavailable"


def test_llm_status_follows_the_circuit_breaker_and_is_cached() -> None:
    world = World(llm_responses=[], llm_status="available")
    assert world.capabilities.current().llm_interpreter is InterpreterStatus.USED
    assert world.llm_status is not None
    world.llm_status.status = "fallback"  # breaker opened
    assert world.capabilities.current().llm_interpreter is InterpreterStatus.USED  # cached
    world.clock.advance(10)
    assert world.capabilities.current().llm_interpreter is InterpreterStatus.FALLBACK


def test_turn_reports_semantic_failures_seen_during_the_search() -> None:
    caps = World().capabilities.for_turn(
        degraded=["semantic_unavailable:model_load_error"], interpreter="deterministic"
    )
    assert caps.semantic is CapabilityStatus.UNAVAILABLE
    assert caps.semantic_reason == "model_load_error"


def test_warnings_are_deduplicated_and_have_messages() -> None:
    caps = Capabilities(
        semantic=CapabilityStatus.UNAVAILABLE,
        llm_interpreter=InterpreterStatus.FALLBACK,
        map=CapabilityStatus.AVAILABLE,
    )
    warnings = turn_warnings(
        ["semantic_unavailable", "semantic_unavailable:timeout", "odd_flag"],
        caps,
        llm_fallback_reason="rate_limited",
    )
    assert [w.code for w in warnings] == ["semantic_unavailable", "odd_flag", "llm_fallback"]
    assert all(w.message for w in warnings)
