from pathlib import Path

import pytest

from music_discovery.infrastructure.settings import AppEnv, Settings, get_settings

ENV_KEYS = (
    "APP_ENV",
    "DATABASE_URL",
    "DISCOGS_TOKEN",
    "OPENROUTER_API_KEY",
    "LLM_PROVIDER",
    "LLM_FALLBACK_MODELS",
    "API_CORS_ORIGINS",
    "DATA_DIR",
    "ARTIFACTS_DIR",
)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def make(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_defaults_load(tmp_path: Path) -> None:
    s = make(project_root=tmp_path)
    assert s.app_env is AppEnv.DEVELOPMENT
    assert s.data_dir == (tmp_path / "data").resolve()
    assert s.embeddings_dir == s.data_dir / "embeddings"
    assert s.umap_dir == s.artifacts_dir / "umap"
    assert s.evaluation_dir == s.data_dir / "evaluation"
    assert s.discogs_token is None
    assert s.llm_enabled is False
    assert s.llm_fallback_models == []


def test_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_DIR", "custom-data")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "a/model:free, b/model:free")
    monkeypatch.setenv("API_CORS_ORIGINS", "http://a.test,http://b.test")
    s = make(project_root=tmp_path)
    assert s.app_env is AppEnv.TEST
    assert s.data_dir == (tmp_path / "custom-data").resolve()
    assert s.llm_enabled is True
    assert s.llm_fallback_models == ["a/model:free", "b/model:free"]
    assert s.api_cors_origins == ["http://a.test", "http://b.test"]


def test_empty_env_values_are_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCOGS_TOKEN", "")
    monkeypatch.setenv("LLM_PROVIDER", "")
    s = make()
    assert s.discogs_token is None
    assert s.llm_provider is None


def test_absolute_paths_kept(tmp_path: Path) -> None:
    s = make(data_dir=tmp_path / "abs")
    assert s.data_dir == tmp_path / "abs"


def test_secrets_never_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCOGS_TOKEN", "discogs-secret-123")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret-456")
    fake_url = "postgresql://user:db-pass-789@host/db"  # pragma: allowlist secret
    monkeypatch.setenv("DATABASE_URL", fake_url)
    s = make()
    assert s.discogs_token is not None
    assert s.discogs_token.get_secret_value() == "discogs-secret-123"
    for text in (repr(s), str(s), str(s.redacted())):
        assert "discogs-secret-123" not in text
        assert "sk-or-secret-456" not in text
    assert "db-pass-789" not in str(s.redacted())
    assert "db-pass-789" not in repr(s)
    assert s.redacted()["database_url"] == "postgresql://user:**********@host/db"


def test_get_settings_returns_fresh_instances() -> None:
    assert get_settings() is not get_settings()


def test_settings_are_immutable() -> None:
    s = make()
    with pytest.raises(ValueError, match="frozen"):
        s.umap_random_state = 1  # type: ignore[misc]
