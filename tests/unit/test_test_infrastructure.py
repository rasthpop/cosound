from pathlib import Path

import pytest

from music_discovery.infrastructure.settings import AppEnv, Settings
from tests.fakes import FrozenClock, SequentialIdGenerator

pytest_plugins = ["pytester"]


def test_settings_fixture_uses_temp_dirs(settings: Settings, tmp_path: Path) -> None:
    assert settings.app_env is AppEnv.TEST
    assert settings.data_dir == tmp_path / "data"
    assert settings.embeddings_dir.is_dir()
    assert settings.umap_dir.is_dir()


def test_frozen_clock_only_moves_when_advanced(clock: FrozenClock) -> None:
    start = clock.now()
    assert clock.now() == start
    clock.sleep(1.5)
    assert (clock.now() - start).total_seconds() == 1.5


def test_id_generator_is_deterministic_per_prefix(id_generator: SequentialIdGenerator) -> None:
    assert [id_generator.new("ses"), id_generator.new("ses"), id_generator.new("qry")] == [
        "ses_000001",
        "ses_000002",
        "qry_000001",
    ]


SAMPLE = """
import pytest

@pytest.mark.slow
def test_slow():
    pass

@pytest.mark.live
def test_live():
    pass

def test_fast():
    pass
"""


@pytest.fixture
def sample_suite(pytester: pytest.Pytester) -> pytest.Pytester:
    conftest = Path(__file__).parents[1] / "conftest.py"
    pytester.makeconftest(conftest.read_text())
    pytester.makeini(
        "[pytest]\nmarkers =\n    slow: slow\n    live: live\n"
        "    unit: u\n    integration: i\n    api: a\n    evaluation: e\n"
    )
    pytester.makepyfile(test_sample=SAMPLE)
    return pytester


def test_slow_and_live_skipped_by_default(sample_suite: pytest.Pytester) -> None:
    result = sample_suite.runpytest()
    result.assert_outcomes(passed=1, skipped=2)


def test_run_slow_selects_slow_tests(sample_suite: pytest.Pytester) -> None:
    result = sample_suite.runpytest("--run-slow")
    result.assert_outcomes(passed=2, skipped=1)


def test_run_live_selects_live_tests(sample_suite: pytest.Pytester) -> None:
    result = sample_suite.runpytest("--run-live")
    result.assert_outcomes(passed=2, skipped=1)
