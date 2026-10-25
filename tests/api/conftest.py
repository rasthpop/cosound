"""TestClient over the app wired with the in-memory test world."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from music_discovery.api.app import create_app
from music_discovery.infrastructure.settings import Settings
from tests.support.world import World

ClientFactory = Callable[..., TestClient]


@pytest.fixture
def make_client(make_settings: Callable[..., Settings], tmp_path: Path) -> ClientFactory:
    """`make_client(**world_options)` -> (client); `client.app.state.world` is the World."""

    def factory(**options: object) -> TestClient:
        options.setdefault("data_dir", tmp_path / "data")
        world = World(**options)  # type: ignore[arg-type]
        app = create_app(make_settings(), services=world.services())
        app.state.world = world
        return TestClient(app, raise_server_exceptions=False)

    return factory


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    return make_client()
