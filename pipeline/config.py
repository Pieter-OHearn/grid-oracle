"""Configuration validation for explicit pipeline operations."""

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when an explicit pipeline operation lacks configuration."""


@dataclass(frozen=True)
class PipelineSettings:
    database_url: str
    openweather_api_key: str | None
    durable_scheduler_enabled: bool


def load_pipeline_settings(env: dict[str, str] | None = None, *, require_weather_key: bool = False) -> PipelineSettings:
    """Validate settings without starting a scheduler or contacting providers."""
    values = os.environ if env is None else env
    database_url = values.get("DATABASE_URL", "").strip()
    if not database_url:
        raise ConfigurationError("DATABASE_URL is required. Copy .env.example to .env and set DATABASE_URL.")
    if urlparse(database_url).scheme not in {"postgresql", "postgresql+psycopg2", "sqlite"}:
        raise ConfigurationError("DATABASE_URL must use postgresql://, postgresql+psycopg2://, or sqlite://.")

    weather_key = values.get("OPENWEATHER_API_KEY", "").strip() or None
    if require_weather_key and not weather_key:
        raise ConfigurationError(
            "OPENWEATHER_API_KEY is required for scheduler mode; sample mode never starts the scheduler."
        )
    durable = values.get("GRIDORACLE_DURABLE_SCHEDULER", "").strip().lower() in {"1", "true", "yes"}
    return PipelineSettings(
        database_url=database_url,
        openweather_api_key=weather_key,
        durable_scheduler_enabled=durable,
    )
