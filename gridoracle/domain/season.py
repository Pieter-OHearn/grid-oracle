"""Validated, data-only season import contract."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SessionKind(StrEnum):
    PRACTICE_1 = "practice_1"
    PRACTICE_2 = "practice_2"
    PRACTICE_3 = "practice_3"
    SPRINT_QUALIFYING = "sprint_qualifying"
    SPRINT = "sprint"
    QUALIFYING = "qualifying"
    RACE = "race"


class EventState(StrEnum):
    SCHEDULED = "scheduled"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class SessionImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SessionKind
    scheduled_at: datetime


class EntryImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver_identity_key: str = Field(pattern=r"^[a-z][a-z0-9_:-]+$")
    team_identity_key: str = Field(pattern=r"^[a-z][a-z0-9_:-]+$")
    role: str = Field(pattern=r"^(primary|reserve)$")


class EventImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_key: str = Field(pattern=r"^[a-z][a-z0-9_:-]+$")
    round: int = Field(ge=1)
    name: str = Field(min_length=1)
    circuit_identity_key: str = Field(pattern=r"^[a-z][a-z0-9_:-]+$")
    layout_identity_key: str = Field(pattern=r"^[a-z][a-z0-9_:-]+$")
    state: EventState = EventState.SCHEDULED
    sessions: list[SessionImport] = Field(min_length=1)
    entries: list[EntryImport] = Field(min_length=1)

    @model_validator(mode="after")
    def has_one_race_and_unique_sessions(self) -> "EventImport":
        kinds = [session.kind for session in self.sessions]
        if kinds.count(SessionKind.RACE) != 1:
            raise ValueError("an event must define exactly one race session")
        if len(kinds) != len(set(kinds)):
            raise ValueError("an event may define each session kind only once")
        return self


class SeasonImportConfig(BaseModel):
    """Versioned input for new-season preparation; no provider call is implied."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0$")
    season: int = Field(ge=1950, le=2200)
    ruleset_version: str = Field(min_length=1)
    events: list[EventImport] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_rounds_and_event_keys(self) -> "SeasonImportConfig":
        rounds = [event.round for event in self.events]
        keys = [event.event_key for event in self.events]
        if len(rounds) != len(set(rounds)):
            raise ValueError("event rounds must be unique within a season")
        if len(keys) != len(set(keys)):
            raise ValueError("event keys must be unique within a season")
        return self
