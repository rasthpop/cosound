"""Frontend fixtures and openapi.json are generated, current, and valid against the DTOs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import export_fixtures, export_openapi

from music_discovery.api import schemas
from music_discovery.api.app import build_app
from music_discovery.infrastructure.settings import AppEnv, Settings

FIXTURES = export_fixtures.OUTPUT_DIR
INDEX = json.loads((FIXTURES / export_fixtures.INDEX).read_text(encoding="utf-8"))

# scenarios the UI track builds against (ui-isolated-development §1)
REQUIRED = {
    "search_ok", "search_empty", "search_no_confident_match", "search_needs_clarification",
    "search_semantic_unavailable", "track_detail", "track_detail_no_audio", "neighbors",
    "feedback_refined", "feedback_rejected", "map_points_page1", "map_points_page2",
    "map_unavailable",
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(INDEX))
def test_fixture_validates_against_its_dto(name: str) -> None:
    dto = getattr(schemas, INDEX[name])
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    model = dto.model_validate(data)
    assert model.model_dump(mode="json") == data  # nothing dropped or coerced


def test_fixture_dtos_are_in_the_openapi_document() -> None:
    components = export_openapi.openapi_document()["components"]["schemas"]
    assert set(INDEX.values()) <= set(components)


def test_required_scenarios_and_error_fixtures_exist() -> None:
    assert set(INDEX) >= REQUIRED
    assert any(name.startswith("error_") for name in INDEX)
    assert {Path(p).stem for p in FIXTURES.glob("*.json")} == {*INDEX, "index"}


def test_generated_files_are_current() -> None:
    """Re-running the export scripts would produce no diff."""
    assert export_openapi.OUTPUT.read_text(encoding="utf-8") == export_openapi.render()
    for name, text in export_fixtures.render().items():
        assert (FIXTURES / name).read_text(encoding="utf-8") == text, name


def test_openapi_is_deterministic() -> None:
    settings = Settings(_env_file=None, app_env=AppEnv.TEST)  # type: ignore[call-arg]
    first = json.dumps(build_app(settings).openapi(), sort_keys=True)
    second = json.dumps(build_app(settings).openapi(), sort_keys=True)
    assert first == second
    operation_ids = [
        op["operationId"] for path in json.loads(first)["paths"].values() for op in path.values()
    ]
    assert len(operation_ids) == len(set(operation_ids))
