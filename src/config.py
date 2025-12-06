"""Centralized application settings powered by Pydantic."""

from __future__ import annotations

import os
from typing import Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    loader_batch_size: int = 1
    janitor_batch_size: int = 100
    janitor_max_process_limit: int = 1000
    worker_poll_interval: float = 1.0
    worker_mock_success_rate: float = 0.8

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


def load_prefixed_env(prefix: str) -> Dict[str, str]:
    """Return environment variables that start with the given prefix.

    Keys are normalized by stripping the prefix and lowercasing to align with
    adapter configuration expectations.
    """

    normalized_prefix = prefix.upper()
    return {
        key.removeprefix(normalized_prefix).lower(): value
        for key, value in os.environ.items()
        if key.startswith(normalized_prefix)
    }


settings = Settings()
