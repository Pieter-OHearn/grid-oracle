"""Unit tests for pipeline.ingest.calendar_sync."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd

from pipeline.ingest.calendar_sync import (
    _extract_session_times,
    _is_nat,
    _to_utc_datetime,
    sync_season_calendar,
)


def _make_event_row(**overrides):
    """Build a dict resembling a single FastF1 event schedule row."""
    base = {
        "RoundNumber": 1,
        "EventName": "Bahrain Grand Prix",
        "Country": "Bahrain",
        "Location": "Sakhir",
        "EventDate": pd.Timestamp("2026-03-15"),
        "EventFormat": "conventional",
        "Session1": "Practice 1",
        "Session1DateUtc": pd.Timestamp("2026-03-13 11:30:00"),
        "Session2": "Practice 2",
        "Session2DateUtc": pd.Timestamp("2026-03-13 15:00:00"),
        "Session3": "Practice 3",
        "Session3DateUtc": pd.Timestamp("2026-03-14 12:30:00"),
        "Session4": "Qualifying",
        "Session4DateUtc": pd.Timestamp("2026-03-14 16:00:00"),
        "Session5": "Race",
        "Session5DateUtc": pd.Timestamp("2026-03-15 15:00:00"),
    }
    base.update(overrides)
    return base


def _make_sprint_event_row():
    """Build a sprint weekend event row (2024+ format)."""
    return _make_event_row(
        RoundNumber=2,
        EventName="Chinese Grand Prix",
        Country="China",
        Location="Shanghai",
        EventDate=pd.Timestamp("2026-03-22"),
        EventFormat="sprint_qualifying",
        Session1="Practice 1",
        Session1DateUtc=pd.Timestamp("2026-03-20 03:30:00"),
        Session2="Sprint Qualifying",
        Session2DateUtc=pd.Timestamp("2026-03-20 07:30:00"),
        Session3="Sprint",
        Session3DateUtc=pd.Timestamp("2026-03-21 03:00:00"),
        Session4="Qualifying",
        Session4DateUtc=pd.Timestamp("2026-03-21 07:00:00"),
        Session5="Race",
        Session5DateUtc=pd.Timestamp("2026-03-22 07:00:00"),
    )


def _mock_engine():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__ = MagicMock(return_value=conn)
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)
    conn.execute.return_value.fetchone.return_value = (1,)
    return engine, conn


# ---------------------------------------------------------------------------
# _extract_session_times
# ---------------------------------------------------------------------------


def test_extract_session_times_conventional():
    row = pd.Series(_make_event_row())
    times = _extract_session_times(row)

    assert len(times) == 5
    assert "Qualifying" in times
    assert "Race" in times
    assert times["Race"] == datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc)


def test_extract_session_times_sprint():
    row = pd.Series(_make_sprint_event_row())
    times = _extract_session_times(row)

    assert len(times) == 5
    assert "Sprint Qualifying" in times
    assert "Sprint" in times
    assert "Qualifying" in times
    assert "Race" in times


def test_extract_session_times_skips_nat():
    data = _make_event_row(Session3DateUtc=pd.NaT)
    row = pd.Series(data)
    times = _extract_session_times(row)

    assert "Practice 3" not in times
    assert len(times) == 4


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_is_nat_with_nat():
    assert _is_nat(pd.NaT) is True


def test_is_nat_with_timestamp():
    assert _is_nat(pd.Timestamp("2026-01-01")) is False


def test_to_utc_datetime_naive():
    naive = datetime(2026, 3, 15, 15, 0)
    result = _to_utc_datetime(naive)
    assert result.tzinfo == timezone.utc


def test_to_utc_datetime_pandas_timestamp():
    ts = pd.Timestamp("2026-03-15 15:00:00")
    result = _to_utc_datetime(ts)
    assert isinstance(result, datetime)
    assert result.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# sync_season_calendar
# ---------------------------------------------------------------------------


@patch("pipeline.ingest.calendar_sync.fastf1.get_event_schedule")
def test_sync_returns_events_with_session_times(mock_schedule):
    mock_schedule.return_value = pd.DataFrame([_make_event_row()])
    engine, _conn = _mock_engine()

    events = sync_season_calendar(2026, engine)

    assert len(events) == 1
    ev = events[0]
    assert ev["season"] == 2026
    assert ev["round"] == 1
    assert ev["name"] == "Bahrain Grand Prix"
    assert ev["race_id"] == 1
    assert ev["event_format"] == "conventional"
    assert "Qualifying" in ev["session_times"]
    assert "Race" in ev["session_times"]


@patch("pipeline.ingest.calendar_sync.fastf1.get_event_schedule")
def test_sync_handles_sprint_weekend(mock_schedule):
    mock_schedule.return_value = pd.DataFrame([_make_sprint_event_row()])
    engine, _conn = _mock_engine()

    events = sync_season_calendar(2026, engine)

    assert len(events) == 1
    ev = events[0]
    assert ev["event_format"] == "sprint_qualifying"
    assert "Sprint Qualifying" in ev["session_times"]
    assert "Sprint" in ev["session_times"]
    assert "Qualifying" in ev["session_times"]
    assert "Race" in ev["session_times"]


@patch("pipeline.ingest.calendar_sync.fastf1.get_event_schedule")
def test_sync_multiple_events(mock_schedule):
    mock_schedule.return_value = pd.DataFrame([_make_event_row(), _make_sprint_event_row()])
    engine, _conn = _mock_engine()

    events = sync_season_calendar(2026, engine)

    assert len(events) == 2
    assert events[0]["round"] == 1
    assert events[1]["round"] == 2
