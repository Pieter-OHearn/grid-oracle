"""Unit tests for pipeline.scheduler."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from pipeline.scheduler import (
    JOB_QUALIFYING,
    JOB_RACE,
    JOB_WEATHER_INITIAL,
    JOB_WEATHER_REFRESH,
    QUALIFYING_GRACE_MINUTES,
    RACE_GRACE_MINUTES,
    WEATHER_INITIAL_DAYS_BEFORE,
    WEATHER_REFRESH_AFTER_QUALI_MINUTES,
    _compute_job_times,
    _find_session_time,
    _list_jobs,
    _make_job_id,
    _run_job,
    _schedule_events,
    _should_catch_up,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conventional_event(
    *,
    season: int = 2026,
    round_num: int = 1,
    race_id: int = 10,
    quali_dt: datetime | None = None,
    race_dt: datetime | None = None,
) -> dict:
    """Build a conventional-weekend event dict."""
    if quali_dt is None:
        quali_dt = datetime(2026, 3, 14, 16, 0, tzinfo=timezone.utc)
    if race_dt is None:
        race_dt = datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc)
    return {
        "season": season,
        "round": round_num,
        "name": "Bahrain Grand Prix",
        "race_id": race_id,
        "event_date": quali_dt.date(),
        "event_format": "conventional",
        "session_times": {
            "Practice 1": datetime(2026, 3, 13, 11, 30, tzinfo=timezone.utc),
            "Practice 2": datetime(2026, 3, 13, 15, 0, tzinfo=timezone.utc),
            "Practice 3": datetime(2026, 3, 14, 12, 30, tzinfo=timezone.utc),
            "Qualifying": quali_dt,
            "Race": race_dt,
        },
    }


def _make_sprint_event(
    *,
    season: int = 2026,
    round_num: int = 2,
    race_id: int = 20,
    quali_dt: datetime | None = None,
    race_dt: datetime | None = None,
) -> dict:
    """Build a sprint-weekend event dict (2024+ format)."""
    if quali_dt is None:
        quali_dt = datetime(2026, 3, 21, 7, 0, tzinfo=timezone.utc)
    if race_dt is None:
        race_dt = datetime(2026, 3, 22, 7, 0, tzinfo=timezone.utc)
    return {
        "season": season,
        "round": round_num,
        "name": "Chinese Grand Prix",
        "race_id": race_id,
        "event_date": quali_dt.date(),
        "event_format": "sprint_qualifying",
        "session_times": {
            "Practice 1": datetime(2026, 3, 20, 3, 30, tzinfo=timezone.utc),
            "Sprint Qualifying": datetime(2026, 3, 20, 7, 30, tzinfo=timezone.utc),
            "Sprint": datetime(2026, 3, 21, 3, 0, tzinfo=timezone.utc),
            "Qualifying": quali_dt,
            "Race": race_dt,
        },
    }


def _mock_engine_with_scalar(value):
    """Return a mock engine whose conn.execute().scalar() returns *value*."""
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__ = MagicMock(return_value=conn)
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)
    conn.execute.return_value.scalar.return_value = value
    return engine, conn


def _mock_engine_with_fetchone(row):
    """Return a mock engine whose conn.execute().fetchone() returns *row*."""
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__ = MagicMock(return_value=conn)
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)
    conn.execute.return_value.fetchone.return_value = row
    return engine, conn


# ---------------------------------------------------------------------------
# _find_session_time
# ---------------------------------------------------------------------------


def test_find_session_time_exact_match():
    times = {"Qualifying": datetime(2026, 3, 14, 16, 0, tzinfo=timezone.utc)}
    assert _find_session_time(times, "Qualifying") == datetime(2026, 3, 14, 16, 0, tzinfo=timezone.utc)


def test_find_session_time_case_insensitive():
    times = {"Qualifying": datetime(2026, 3, 14, 16, 0, tzinfo=timezone.utc)}
    assert _find_session_time(times, "qualifying") is not None


def test_find_session_time_missing_returns_none():
    assert _find_session_time({}, "Race") is None


# ---------------------------------------------------------------------------
# _compute_job_times — conventional weekend
# ---------------------------------------------------------------------------


def test_compute_job_times_conventional_weekend():
    event = _make_conventional_event()
    jobs = _compute_job_times(event)

    job_dict = dict(jobs)
    assert len(job_dict) == 4, f"Expected 4 jobs, got {len(job_dict)}: {list(job_dict.keys())}"

    quali_time = event["session_times"]["Qualifying"]
    race_time = event["session_times"]["Race"]

    assert job_dict[JOB_WEATHER_INITIAL] == race_time - timedelta(days=WEATHER_INITIAL_DAYS_BEFORE)
    assert job_dict[JOB_WEATHER_REFRESH] == quali_time + timedelta(minutes=WEATHER_REFRESH_AFTER_QUALI_MINUTES)
    assert job_dict[JOB_QUALIFYING] == quali_time + timedelta(minutes=QUALIFYING_GRACE_MINUTES)
    assert job_dict[JOB_RACE] == race_time + timedelta(minutes=RACE_GRACE_MINUTES)


# ---------------------------------------------------------------------------
# _compute_job_times — sprint weekend
# ---------------------------------------------------------------------------


def test_compute_job_times_sprint_weekend():
    event = _make_sprint_event()
    jobs = _compute_job_times(event)

    job_dict = dict(jobs)
    assert len(job_dict) == 4

    quali_time = event["session_times"]["Qualifying"]
    race_time = event["session_times"]["Race"]

    assert job_dict[JOB_WEATHER_INITIAL] == race_time - timedelta(days=WEATHER_INITIAL_DAYS_BEFORE)
    assert job_dict[JOB_WEATHER_REFRESH] == quali_time + timedelta(minutes=WEATHER_REFRESH_AFTER_QUALI_MINUTES)
    assert job_dict[JOB_QUALIFYING] == quali_time + timedelta(minutes=QUALIFYING_GRACE_MINUTES)
    assert job_dict[JOB_RACE] == race_time + timedelta(minutes=RACE_GRACE_MINUTES)


# ---------------------------------------------------------------------------
# _compute_job_times — missing sessions
# ---------------------------------------------------------------------------


def test_compute_job_times_missing_qualifying():
    """Only weather_initial and race_results if Qualifying is absent."""
    event = _make_conventional_event()
    del event["session_times"]["Qualifying"]
    jobs = _compute_job_times(event)
    job_types = [jt for jt, _ in jobs]
    assert JOB_WEATHER_INITIAL in job_types
    assert JOB_RACE in job_types
    assert JOB_QUALIFYING not in job_types
    assert JOB_WEATHER_REFRESH not in job_types


def test_compute_job_times_missing_race():
    """Only weather_refresh and qualifying_results if Race is absent."""
    event = _make_conventional_event()
    del event["session_times"]["Race"]
    jobs = _compute_job_times(event)
    job_types = [jt for jt, _ in jobs]
    assert JOB_WEATHER_REFRESH in job_types
    assert JOB_QUALIFYING in job_types
    assert JOB_WEATHER_INITIAL not in job_types
    assert JOB_RACE not in job_types


# ---------------------------------------------------------------------------
# _make_job_id
# ---------------------------------------------------------------------------


def test_make_job_id_format():
    assert _make_job_id(JOB_QUALIFYING, 2026, 5) == "qualifying_results_2026_R05"
    assert _make_job_id(JOB_RACE, 2026, 12) == "race_results_2026_R12"


# ---------------------------------------------------------------------------
# _run_job
# ---------------------------------------------------------------------------


@patch("pipeline.scheduler.fetch_and_store_weather")
def test_run_job_weather_initial(mock_weather):
    engine = MagicMock()
    _run_job(JOB_WEATHER_INITIAL, 2026, 1, 10, engine)
    mock_weather.assert_called_once_with(10, engine)


@patch("pipeline.scheduler.fetch_and_store_weather")
def test_run_job_weather_refresh(mock_weather):
    engine = MagicMock()
    _run_job(JOB_WEATHER_REFRESH, 2026, 1, 10, engine)
    mock_weather.assert_called_once_with(10, engine)


@patch("pipeline.scheduler.ingest_qualifying_event")
def test_run_job_qualifying(mock_quali):
    engine = MagicMock()
    _run_job(JOB_QUALIFYING, 2026, 3, 30, engine)
    mock_quali.assert_called_once_with(2026, 3, engine)


@patch("pipeline.scheduler.ingest_results_event")
def test_run_job_race(mock_race):
    engine = MagicMock()
    _run_job(JOB_RACE, 2026, 3, 30, engine)
    mock_race.assert_called_once_with(2026, 3, engine)


@patch("pipeline.scheduler.ingest_results_event", side_effect=Exception("boom"))
def test_run_job_logs_exception(mock_race):
    """Job failures are caught and logged, not raised."""
    engine = MagicMock()
    _run_job(JOB_RACE, 2026, 1, 10, engine)  # Should not raise


# ---------------------------------------------------------------------------
# _should_catch_up
# ---------------------------------------------------------------------------


def test_catch_up_qualifying_data_absent():
    engine, _conn = _mock_engine_with_scalar(0)  # COUNT(*) = 0
    event = _make_conventional_event()
    assert _should_catch_up(JOB_QUALIFYING, event, engine) is True


def test_catch_up_qualifying_data_present():
    engine, _conn = _mock_engine_with_scalar(20)  # COUNT(*) = 20
    event = _make_conventional_event()
    assert _should_catch_up(JOB_QUALIFYING, event, engine) is False


def test_catch_up_race_data_absent_not_completed():
    engine, _conn = _mock_engine_with_fetchone((False, 0))
    event = _make_conventional_event()
    assert _should_catch_up(JOB_RACE, event, engine) is True


def test_catch_up_race_already_completed():
    engine, _conn = _mock_engine_with_fetchone((True, 20))
    event = _make_conventional_event()
    assert _should_catch_up(JOB_RACE, event, engine) is False


def test_catch_up_weather_initial_future_race():
    engine, _conn = _mock_engine_with_scalar(False)  # is_completed = False
    future_race = datetime.now(timezone.utc) + timedelta(days=3)
    event = _make_conventional_event(race_dt=future_race)
    assert _should_catch_up(JOB_WEATHER_INITIAL, event, engine) is True


def test_catch_up_weather_initial_past_race():
    engine, _conn = _mock_engine_with_scalar(False)
    past_race = datetime.now(timezone.utc) - timedelta(days=3)
    event = _make_conventional_event(race_dt=past_race)
    assert _should_catch_up(JOB_WEATHER_INITIAL, event, engine) is False


def test_catch_up_weather_refresh_between_quali_and_race():
    engine, _conn = _mock_engine_with_scalar(False)  # is_completed = False
    now = datetime.now(timezone.utc)
    event = _make_conventional_event(
        quali_dt=now - timedelta(hours=2),
        race_dt=now + timedelta(hours=12),
    )
    assert _should_catch_up(JOB_WEATHER_REFRESH, event, engine) is True


def test_catch_up_weather_refresh_race_already_past():
    engine, _conn = _mock_engine_with_scalar(False)
    now = datetime.now(timezone.utc)
    event = _make_conventional_event(
        quali_dt=now - timedelta(days=2),
        race_dt=now - timedelta(days=1),
    )
    assert _should_catch_up(JOB_WEATHER_REFRESH, event, engine) is False


# ---------------------------------------------------------------------------
# _schedule_events
# ---------------------------------------------------------------------------


@patch("pipeline.scheduler._should_catch_up", return_value=False)
@patch("pipeline.scheduler.datetime")
def test_schedule_events_registers_future_jobs(mock_dt, mock_catchup):
    """Future jobs are added to the scheduler."""
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    mock_dt.now.return_value = now
    mock_dt.min = datetime.min
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    scheduler = MagicMock()
    engine = MagicMock()

    # All session times are in the future relative to our mocked "now"
    event = _make_conventional_event()
    _schedule_events(scheduler, [event], engine)

    # 4 jobs should be registered
    assert scheduler.add_job.call_count == 4


@patch("pipeline.scheduler._run_job")
@patch("pipeline.scheduler._should_catch_up", return_value=True)
@patch("pipeline.scheduler.datetime")
def test_schedule_events_catches_up_past_jobs(mock_dt, mock_catchup, mock_run):
    """Past jobs with missing data trigger catch-up."""
    now = datetime(2026, 12, 1, tzinfo=timezone.utc)
    mock_dt.now.return_value = now
    mock_dt.min = datetime.min
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    scheduler = MagicMock()
    engine = MagicMock()

    # All session times are in the past relative to our mocked "now"
    event = _make_conventional_event()
    _schedule_events(scheduler, [event], engine)

    # No jobs added to scheduler (all in the past)
    scheduler.add_job.assert_not_called()
    # catch-up runs were triggered
    assert mock_run.call_count == 4


# ---------------------------------------------------------------------------
# _list_jobs
# ---------------------------------------------------------------------------


def test_list_jobs_no_jobs(caplog):
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    with caplog.at_level("INFO"):
        _list_jobs(scheduler)
    assert "No future jobs scheduled" in caplog.text


def test_list_jobs_with_jobs(caplog):
    job = MagicMock()
    job.id = "qualifying_results_2026_R01"
    job.next_run_time = datetime(2026, 3, 14, 16, 45, tzinfo=timezone.utc)

    scheduler = MagicMock()
    scheduler.get_jobs.return_value = [job]
    with caplog.at_level("INFO"):
        _list_jobs(scheduler)
    assert "qualifying_results_2026_R01" in caplog.text
    assert "Scheduled jobs (1)" in caplog.text


# ---------------------------------------------------------------------------
# _manual_trigger
# ---------------------------------------------------------------------------


@patch("pipeline.scheduler._run_job")
@patch("pipeline.scheduler.sync_season_calendar")
def test_manual_trigger_calls_run_job(mock_sync, mock_run):
    from pipeline.scheduler import _manual_trigger

    mock_sync.return_value = [_make_conventional_event()]
    engine = MagicMock()

    _manual_trigger(JOB_QUALIFYING, 2026, 1, engine)

    mock_run.assert_called_once_with(JOB_QUALIFYING, 2026, 1, 10, engine)


@patch("pipeline.scheduler.sync_season_calendar")
def test_manual_trigger_exits_on_missing_round(mock_sync):
    import pytest

    from pipeline.scheduler import _manual_trigger

    mock_sync.return_value = [_make_conventional_event()]
    engine = MagicMock()

    with pytest.raises(SystemExit):
        _manual_trigger(JOB_QUALIFYING, 2026, 99, engine)


# ---------------------------------------------------------------------------
# Weather timing
# ---------------------------------------------------------------------------


def test_weather_initial_timing_5_days_before_race():
    race_dt = datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc)
    event = _make_conventional_event(race_dt=race_dt)
    jobs = dict(_compute_job_times(event))

    expected = race_dt - timedelta(days=5)
    assert jobs[JOB_WEATHER_INITIAL] == expected
    assert expected == datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc)


def test_weather_refresh_timing_30_min_after_quali():
    quali_dt = datetime(2026, 3, 14, 16, 0, tzinfo=timezone.utc)
    event = _make_conventional_event(quali_dt=quali_dt)
    jobs = dict(_compute_job_times(event))

    expected = quali_dt + timedelta(minutes=30)
    assert jobs[JOB_WEATHER_REFRESH] == expected
    assert expected == datetime(2026, 3, 14, 16, 30, tzinfo=timezone.utc)
