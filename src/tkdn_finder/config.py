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

    homepage_url: str = "https://p3dn.kemenperin.go.id/rekap.php"
    user_agent: str = "TKDN-Finder/0.1 (procurement tooling)"
    download_timeout_seconds: int = 120
    retry_count: int = 3
    retry_backoff_seconds: int = 5
    # P3DN uses a cert that fails verification on some corporate proxies (SSL inspection).
    # Defaulting to False; override with TKDN_P3DN__VERIFY_SSL=true if your network is clean.
    verify_ssl: bool = False

    model_config = SettingsConfigDict(env_prefix="TKDN_P3DN__")


class ScheduleSettings(BaseSettings):
    """APScheduler configuration."""

    enabled: bool = True
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
        """Compute the SQLite database path, using APPDATA on Windows."""
        if os.name == "nt":
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            base = os.path.join(appdata, "TKDN-Finder")
        else:
            base = self.data_dir
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "tkdn.db")

    def get_raw_dir(self) -> str:
        """Compute the raw download directory."""
        if os.name == "nt":
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            base = os.path.join(appdata, "TKDN-Finder", "raw")
        else:
            base = os.path.join(self.data_dir, "raw")
        os.makedirs(base, exist_ok=True)
        return base


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
