"""Configuration validation for the HTTP service.

The API deliberately has no production database default.  A missing setting
should fail before the service creates a connection or exposes an endpoint.
"""

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when a required GridOracle setting is absent or invalid."""


@dataclass(frozen=True)
class ApiSettings:
    database_url: str
    cors_origin: str


def _required(name: str, env: dict[str, str]) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigurationError(
            f"{name} is required. Copy .env.example to .env and set {name}."
        )
    return value


def load_api_settings(env: dict[str, str] | None = None) -> ApiSettings:
    """Return validated API settings without mutating process environment."""
    values = os.environ if env is None else env
    database_url = _required("DATABASE_URL", values)
    accepted_schemes = {"postgresql", "postgresql+psycopg2", "sqlite"}
    if urlparse(database_url).scheme not in accepted_schemes:
        raise ConfigurationError(
            "DATABASE_URL must use postgresql://, postgresql+psycopg2://, or sqlite://."
        )

    cors_origin = values.get("CORS_ORIGIN", "http://localhost:3000").strip()
    parsed_origin = urlparse(cors_origin)
    if parsed_origin.scheme not in {"http", "https"} or not parsed_origin.netloc:
        raise ConfigurationError(
            "CORS_ORIGIN must be a single http(s) origin, for example "
            "http://localhost:3000."
        )
    return ApiSettings(database_url=database_url, cors_origin=cors_origin)
