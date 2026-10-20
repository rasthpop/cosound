"""Shared pytest configuration: opt-in slow/live tests, directory markers, common fixtures."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from music_discovery.infrastructure.settings import AppEnv, Settings
from tests.fakes import FrozenClock, SequentialIdGenerator

TESTS_DIR = Path(__file__).parent
DIRECTORY_MARKERS = ("unit", "integration", "api", "evaluation")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--run-slow", action="store_true", help="run tests marked slow")
    parser.addoption("--run-live", action="store_true", help="run tests marked live")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip_slow = pytest.mark.skip(reason="slow test: use --run-slow")
    skip_live = pytest.mark.skip(reason="live external service: use --run-live")
    for item in items:
        parts = Path(item.fspath).relative_to(TESTS_DIR).parts
        if parts and parts[0] in DIRECTORY_MARKERS:
            item.add_marker(getattr(pytest.mark, parts[0]))
        if "slow" in item.keywords and not config.getoption("--run-slow"):
            item.add_marker(skip_slow)
        if "live" in item.keywords and not config.getoption("--run-live"):
            item.add_marker(skip_live)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Empty data directory with the standard layout."""
    root = tmp_path / "data"
    for sub in ("raw", "processed", "embeddings", "indexes", "evaluation"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture
def artifacts_dir(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    for sub in ("umap", "evaluation"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture
def make_settings(tmp_path: Path, data_dir: Path, artifacts_dir: Path) -> Callable[..., Settings]:
    """Settings isolated from the developer's `.env`, pointing at temp directories."""

    def factory(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "app_env": AppEnv.TEST,
            "project_root": tmp_path,
            "data_dir": data_dir,
            "artifacts_dir": artifacts_dir,
            "database_url": f"sqlite:///{tmp_path / 'test.db'}",
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)  # type: ignore[call-arg]

    return factory


@pytest.fixture
def settings(make_settings: Callable[..., Settings]) -> Settings:
    return make_settings()


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock()


@pytest.fixture
def id_generator() -> SequentialIdGenerator:
    return SequentialIdGenerator()
