"""Versioned, allowlisted public DTOs. Internal manifests never cross this boundary."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Horizon = Literal["pre_weekend", "post_qualifying"]


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Coverage(PublicModel):
    state: Literal["complete", "partial", "unknown", "empty"]
    available: int | None = Field(ge=0)
    expected: int | None = Field(default=None, ge=0)
    reason: str | None = None


class Freshness(PublicModel):
    state: Literal["verified_as_of_cutoff", "source_late", "stale", "unknown"]
    input_cutoff_at: datetime | None
    issued_at: datetime | None
    source_available_at: datetime | None
    reason: str | None = None


class Season(PublicModel):
    year: int
    ruleset_version: str | None
    coverage: Coverage


class SeasonIndex(PublicModel):
    seasons: list[Season]


class Event(PublicModel):
    id: int
    event_key: str
    season: int
    round: int
    name: str
    date: date
    lifecycle: Literal["scheduled", "postponed", "cancelled", "completed"]
    circuit_name: str | None
    coverage: Coverage


class EventIndex(PublicModel):
    season: int
    events: list[Event]


class EventSession(PublicModel):
    id: int
    kind: str
    scheduled_at: datetime
    revision: int
    status: str


class SessionIndex(PublicModel):
    season: int
    event_id: int
    sessions: list[EventSession]


class PublicEntry(PublicModel):
    entry_key: str
    driver_name: str | None
    team_name: str | None
    team_color: str | None = None
    win_probability: float | None = Field(ge=0, le=1)


class PublishedRun(PublicModel):
    run_id: str
    season: int
    event_id: int
    horizon: Horizon
    published_at: datetime
    provenance: Literal["verified", "observed"]
    freshness: Freshness
    coverage: Coverage
    entries: list[PublicEntry]


class PublishedForecast(PublicModel):
    state: Literal["published"] = "published"
    reason: None = None
    run: PublishedRun


class UnavailableForecast(PublicModel):
    state: Literal["unavailable"] = "unavailable"
    reason: Literal["no_published_forecast"] = "no_published_forecast"
    run: None = None


ForecastSelection = PublishedForecast | UnavailableForecast


class RunIndex(PublicModel):
    season: int
    event_id: int
    runs: list[PublishedRun]


class PublicError(PublicModel):
    code: Literal[
        "not_found", "invalid_request", "api_unavailable", "invalid_publication"
    ]
    message: str
    retryable: bool


class ErrorResponse(PublicModel):
    error: PublicError
