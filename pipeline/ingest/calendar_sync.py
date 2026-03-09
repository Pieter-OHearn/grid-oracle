"""Sync the FastF1 event calendar to the races/circuits tables."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import fastf1
import pandas as pd
from sqlalchemy.engine import Engine

from pipeline.ingest.upsert_helpers import upsert_circuit_from_event, upsert_race

logger = logging.getLogger(__name__)


def sync_season_calendar(season: int, engine: Engine) -> list[dict]:
    """Load the FastF1 event schedule and upsert circuits + races.

    Returns a list of event dicts with keys:
      - season, round, name, race_id, event_date
      - session_times: dict mapping session name -> datetime (UTC)
      - event_format: str ("conventional", "sprint_qualifying", etc.)
    """
    schedule = fastf1.get_event_schedule(season, include_testing=False)
    logger.info("Calendar sync: season %d — %d events", season, len(schedule))

    events: list[dict] = []
    for _, event in schedule.iterrows():
        round_num = int(event["RoundNumber"])
        event_name = event["EventName"]
        country = event["Country"]
        location = event["Location"]
        event_date = event["EventDate"].date() if hasattr(event["EventDate"], "date") else event["EventDate"]
        event_format = str(event.get("EventFormat", "conventional"))

        try:
            with engine.begin() as conn:
                circuit_id = upsert_circuit_from_event(conn, event_name, country, location)
                race_id = upsert_race(
                    conn,
                    season,
                    round_num,
                    event_name,
                    circuit_id,
                    event_date,
                    mark_completed=False,
                )
        except Exception:
            logger.exception("Round %d — %s: failed to upsert, skipping", round_num, event_name)
            continue

        session_times = _extract_session_times(event)

        events.append(
            {
                "season": season,
                "round": round_num,
                "name": event_name,
                "race_id": race_id,
                "event_date": event_date,
                "event_format": event_format,
                "session_times": session_times,
            }
        )

        logger.info(
            "  Round %d — %s (id=%d, format=%s, sessions=%s)",
            round_num,
            event_name,
            race_id,
            event_format,
            list(session_times.keys()),
        )

    return events


def _extract_session_times(event: Any) -> dict[str, datetime]:
    """Extract session name -> UTC datetime mapping from an event row."""
    session_times: dict[str, datetime] = {}
    for i in range(1, 6):
        s_name = event.get(f"Session{i}")
        s_date = event.get(f"Session{i}DateUtc")
        if s_name and s_date is not None and not _is_nat(s_date):
            session_times[str(s_name)] = _to_utc_datetime(s_date)
    return session_times


def _is_nat(val: Any) -> bool:
    """Check if a value is NaT (Not a Time)."""
    try:
        return pd.isna(val)
    except (TypeError, ValueError):
        return False


def _to_utc_datetime(val: Any) -> datetime:
    """Convert a pandas Timestamp or naive datetime to timezone-aware UTC."""
    if hasattr(val, "to_pydatetime"):
        val = val.to_pydatetime()
    if val.tzinfo is None:
        val = val.replace(tzinfo=timezone.utc)
    return val
