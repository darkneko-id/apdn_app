# src/tkdn_finder/config.py
"""Typed configuration via pydantic-settings. Precedence: env > yaml > defaults."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class P3dnSettings(BaseSettings):
    """P3DN portal connection settings."""

    homepage_url: str = "https://p3dn.kemenperin.go.id/"
    user_agent: str = "TKDN-Finder/0.1 (procurement tooling)"
    download_timeout_seconds: int = 120
    retry_count: int = 3
    retry_backoff_seconds: int = 5

    model_config = SettingsConfigDict(env_prefix="TKDN_P3DN__")


class ScheduleSettings(BaseSettings):
    """APScheduler configuration."""

    cron: str = "0 2 * * *"

    model_config = SettingsConfigDict(env_prefix="TKDN_SCHEDULE__")


class Settings(BaseSettings):
    """Top-level application settings."""

    data_dir: str = "data"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000
    p3dn: P3dnSettings = Field(default_factory=P3dnSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        env_prefix="TKDN_",
        extra="ignore",
    )

    def get_db_path(self) -> str:
        """Compute the SQLite database path from data_dir."""
        return os.path.join(self.data_dir, "tkdn.db")

    def get_raw_dir(self) -> str:
        """Compute the raw download directory."""
        return os.path.join(self.data_dir, "raw")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
