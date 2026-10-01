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
    source_name: str | None = None
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


class PerformanceMetric(PublicModel):
    key: Literal[
        "winner_log_loss",
        "winner_hit",
        "winner_brier",
        "rank_mae",
        "rank_correlation",
        "top3_overlap",
        "top10_overlap",
        "ece",
    ]
    label: str
    outcome: str
    value: float | None = Field(allow_inf_nan=False)
    unit: Literal["fraction", "loss", "positions", "correlation"]
    observations: int | None = Field(ge=0)


class ReliabilityBin(PublicModel):
    lower: float
    upper: float
    mean_probability: float | None
    observed_rate: float | None
    entries: int
    races: int


class HistoricalRace(PublicModel):
    season: int
    round: int
    field_entries: int | None
    classified_entries: int | None
    missing_feature_cells: int | None
    winner_log_loss: float | None
    winner_hit: float | None
    top3_overlap: float | None
    top10_overlap: float | None
    rank_mae: float | None
    missing_reason: str | None


class HistoricalCandidate(PublicModel):
    name: str
    horizon: Horizon
    retained: bool
    expected_races: int
    predicted_races: int
    metrics: list[PerformanceMetric]
    winner_loss_interval: list[float]
    races: list[HistoricalRace]
    reliability: list[ReliabilityBin]


class HistoricalPerformance(PublicModel):
    evidence_id: Literal["wp09-862243fc69d04f5ab9967b8499ca19da"]
    scope: Literal["explored_chronological_reconstruction"]
    candidates: list[HistoricalCandidate]


class PublicEvaluation(PublicModel):
    evaluated_at: datetime
    run_id: str
    result_revision: int
    metrics: list[PerformanceMetric]


class ResultCorrection(PublicModel):
    revision: int
    recorded_at: datetime
    official: bool
    change: Literal["Initial recorded result", "Result correction recorded"]
    evaluations: list[PublicEvaluation]


class EventPerformance(PublicModel):
    season: int
    event_id: int
    event_name: str
    round: int
    horizon: Horizon
    run_id: str | None
    corrections: list[ResultCorrection]
    status: Literal[
        "stored_evaluation", "evaluation_unavailable", "no_published_forecast"
    ]


class LivePerformance(PublicModel):
    season: int
    horizon: Horizon
    events: list[EventPerformance]
