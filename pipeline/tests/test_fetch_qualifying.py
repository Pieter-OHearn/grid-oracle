"""Unit tests for pipeline.ingest.fetch_qualifying."""

from unittest.mock import MagicMock, patch

import pandas as pd

from pipeline.ingest.fetch_qualifying import (
    _interval_or_none,
    _load_race_grid,
    upsert_qualifying_result,
)

# ---------------------------------------------------------------------------
# _interval_or_none
# ---------------------------------------------------------------------------


def test_interval_or_none_with_none():
    assert _interval_or_none(None) is None


def test_interval_or_none_with_nat():
    assert _interval_or_none(pd.NaT) is None


def test_interval_or_none_with_valid_timedelta():
    td = pd.Timedelta(seconds=90, milliseconds=456)
    result = _interval_or_none(td)
    assert result == f"{td.total_seconds()} seconds"


def test_interval_or_none_with_zero():
    td = pd.Timedelta(0)
    assert _interval_or_none(td) == "0.0 seconds"


# ---------------------------------------------------------------------------
# upsert_qualifying_result
# ---------------------------------------------------------------------------


def test_upsert_qualifying_result_executes():
    conn = MagicMock()
    q1 = pd.Timedelta(seconds=90, milliseconds=123)
    q2 = pd.Timedelta(seconds=89, milliseconds=456)
    upsert_qualifying_result(
        conn,
        race_id=1,
        driver_id=2,
        constructor_id=3,
        q1_time=q1,
        q2_time=q2,
        q3_time=None,
        grid_position=5,
    )
    conn.execute.assert_called_once()
    params = conn.execute.call_args[0][1]
    assert params["race_id"] == 1
    assert params["driver_id"] == 2
    assert params["constructor_id"] == 3
    assert params["grid_position"] == 5
    assert params["q1_time"] == f"{q1.total_seconds()} seconds"
    assert params["q3_time"] is None
    assert params["grid_penalty"] is None


def test_upsert_qualifying_result_with_penalty():
    conn = MagicMock()
    upsert_qualifying_result(conn, 1, 2, 3, None, None, None, grid_position=3, grid_penalty=5)
    params = conn.execute.call_args[0][1]
    assert params["grid_position"] == 3
    assert params["grid_penalty"] == 5


def test_upsert_qualifying_result_null_grid_position():
    conn = MagicMock()
    upsert_qualifying_result(conn, 1, 2, 3, None, None, None, grid_position=None)
    params = conn.execute.call_args[0][1]
    assert params["grid_position"] is None
    assert params["grid_penalty"] is None


# ---------------------------------------------------------------------------
# _load_race_grid
# ---------------------------------------------------------------------------


def _make_race_results(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_load_race_grid_returns_grid_positions():
    results = _make_race_results(
        [
            {"Abbreviation": "VER", "GridPosition": 6.0},
            {"Abbreviation": "LEC", "GridPosition": 1.0},
            {"Abbreviation": "HAM", "GridPosition": 4.0},
        ]
    )
    mock_session = MagicMock()
    mock_session.results = results
    with patch("pipeline.ingest.fetch_qualifying.fastf1.get_session", return_value=mock_session):
        grid = _load_race_grid(2023, 12)
    assert grid == {"VER": 6, "LEC": 1, "HAM": 4}


def test_load_race_grid_skips_nan_grid_position():
    results = _make_race_results(
        [
            {"Abbreviation": "VER", "GridPosition": 1.0},
            {"Abbreviation": "PIT", "GridPosition": float("nan")},
        ]
    )
    mock_session = MagicMock()
    mock_session.results = results
    with patch("pipeline.ingest.fetch_qualifying.fastf1.get_session", return_value=mock_session):
        grid = _load_race_grid(2023, 12)
    assert grid == {"VER": 1}
    assert "PIT" not in grid


def test_load_race_grid_returns_empty_when_session_unavailable():
    with patch(
        "pipeline.ingest.fetch_qualifying.fastf1.get_session",
        side_effect=Exception("no data"),
    ):
        grid = _load_race_grid(2026, 5)
    assert grid == {}


def test_load_race_grid_returns_empty_when_results_empty():
    mock_session = MagicMock()
    mock_session.results = pd.DataFrame()
    with patch("pipeline.ingest.fetch_qualifying.fastf1.get_session", return_value=mock_session):
        grid = _load_race_grid(2023, 1)
    assert grid == {}
