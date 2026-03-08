"""Unit tests for pipeline.ingest.fetch_results."""

from unittest.mock import MagicMock

import numpy as np

from pipeline.ingest.fetch_results import upsert_race_result


def test_upsert_race_result_executes():
    conn = MagicMock()
    upsert_race_result(
        conn,
        race_id=1,
        driver_id=2,
        constructor_id=3,
        grid_position=1,
        finish_position=1,
        points=25.0,
        status="Finished",
        fastest_lap=True,
        is_wet_race=False,
    )
    conn.execute.assert_called_once()
    params = conn.execute.call_args[0][1]
    assert params["race_id"] == 1
    assert params["points"] == 25.0
    assert params["fastest_lap"] is True
    assert params["is_wet_race"] is False


def test_upsert_race_result_nan_positions_become_none():
    conn = MagicMock()
    upsert_race_result(
        conn,
        race_id=1,
        driver_id=2,
        constructor_id=3,
        grid_position=np.nan,
        finish_position=np.nan,
        points=0.0,
        status="DNF",
        fastest_lap=False,
        is_wet_race=False,
    )
    params = conn.execute.call_args[0][1]
    assert params["grid_position"] is None
    assert params["finish_position"] is None


def test_upsert_race_result_nan_points_defaults_to_zero():
    conn = MagicMock()
    upsert_race_result(
        conn,
        race_id=1,
        driver_id=2,
        constructor_id=3,
        grid_position=5,
        finish_position=None,
        points=np.nan,
        status="DNF",
        fastest_lap=False,
        is_wet_race=True,
    )
    params = conn.execute.call_args[0][1]
    assert params["points"] == 0.0
    assert params["is_wet_race"] is True
