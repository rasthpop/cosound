"""Environment-based configuration (base.md §15).

Settings are created through `get_settings()` by composition roots (API app, scripts, tests);
no module-level instance exists, so importing this module has no side effects.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# src/music_discovery/infrastructure/settings.py -> repository root
_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = _PACKAGE_ROOT if (_PACKAGE_ROOT / "pyproject.toml").is_file() else Path.cwd()

_URL_PASSWORD = re.compile(r"(?P<prefix>://[^:/@]+:)(?P<password>[^@]+)(?P<suffix>@)")
_REDACTED = "**********"


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


def _split_csv(value: Any) -> Any:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


CsvList = Annotated[list[str], NoDecode]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_env: AppEnv = AppEnv.DEVELOPMENT
    project_root: Path = REPO_ROOT
    database_url: str = Field(default="sqlite:///./music_discovery.db", repr=False)

    discogs_user_agent: str = "SemanticMusicDiscovery/0.1"
    discogs_token: SecretStr | None = None

    clap_checkpoint: Path | None = None
    clap_model_version: str | None = None

    data_dir: Path = Path("./data")
    artifacts_dir: Path = Path("./artifacts")

    umap_random_state: int = 42
    umap_n_components: int = Field(default=2, ge=2, le=3)

    active_embedding_version: str | None = None
    active_projection_version: str | None = None

    llm_provider: str | None = None
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str | None = None
    llm_fallback_models: CsvList = Field(default_factory=list)
    llm_timeout_s: float = Field(default=20.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)
    openrouter_app_title: str = "SemanticMusicDiscovery"
    openrouter_http_referer: str | None = None

    api_cors_origins: CsvList = Field(default_factory=lambda: ["http://localhost:5173"])

    @field_validator("llm_fallback_models", "api_cors_origins", mode="before")
    @classmethod
    def _parse_csv(cls, value: Any) -> Any:
        return _split_csv(value)

    @field_validator(
        "discogs_token",
        "openrouter_api_key",
        "clap_checkpoint",
        "clap_model_version",
        "active_embedding_version",
        "active_projection_version",
        "llm_provider",
        "llm_model",
        "openrouter_http_referer",
        mode="before",
    )
    @classmethod
    def _empty_as_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _resolve_paths(self) -> Settings:
        root = self.project_root.resolve()
        resolved: dict[str, Path] = {"project_root": root}
        for name in ("data_dir", "artifacts_dir", "clap_checkpoint"):
            value = getattr(self, name)
            if value is not None and not value.is_absolute():
                resolved[name] = (root / value).resolve()
        for name, value in resolved.items():
            object.__setattr__(self, name, value)
        return self

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider is not None

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def embeddings_dir(self) -> Path:
        return self.data_dir / "embeddings"

    @property
    def indexes_dir(self) -> Path:
        return self.data_dir / "indexes"

    @property
    def evaluation_dir(self) -> Path:
        """Tracked evaluation inputs (manifest, queries, judgments, split)."""
        return self.data_dir / "evaluation"

    @property
    def llm_cache_dir(self) -> Path:
        return self.data_dir / "llm_cache"

    @property
    def umap_dir(self) -> Path:
        return self.artifacts_dir / "umap"

    @property
    def evaluation_artifacts_dir(self) -> Path:
        return self.artifacts_dir / "evaluation"

    def redacted(self) -> dict[str, Any]:
        """JSON-safe dump for logs and artifact meta files, with every secret masked."""
        dump: dict[str, Any] = self.model_dump(mode="json")
        dump["database_url"] = _URL_PASSWORD.sub(
            lambda m: f"{m['prefix']}{_REDACTED}{m['suffix']}", self.database_url
        )
        return dump


def get_settings(**overrides: Any) -> Settings:
    """Build settings from the environment (and `.env`), with optional explicit overrides."""
    return Settings(**overrides)
