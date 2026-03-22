"""Unit tests for pipeline.features.builder."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from pipeline.features.builder import (
    _championship_position,
    _constructor_dnf_rate_last_season,
    _driver_avg_position_at_circuit,
    _driver_avg_position_last_n,
    _driver_avg_qualifying_position_at_circuit,
    _driver_podium_rate_at_circuit,
    _driver_season_avg_position,
    _driver_wet_race_avg_position,
    _grid_position,
    _is_wet_race_forecast,
    _upsert_feature,
    build_features_for_race,
    export_parquet,
)

# ---------------------------------------------------------------------------
# Scalar feature helpers
# ---------------------------------------------------------------------------


def _mock_conn_scalar(return_value):
    """Create a mock connection whose execute().scalar() returns a value."""
    conn = MagicMock()
    conn.execute.return_value.scalar.return_value = return_value
    return conn


def _mock_conn_fetchone(return_value):
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = return_value
    return conn


def test_grid_position_returns_value():
    conn = _mock_conn_scalar(5)
    assert _grid_position(conn, race_id=1, driver_id=2) == 5


def test_grid_position_returns_none():
    conn = _mock_conn_scalar(None)
    assert _grid_position(conn, race_id=1, driver_id=2) is None


def test_driver_avg_qualifying_position_at_circuit():
    conn = _mock_conn_scalar(6.0)
    result = _driver_avg_qualifying_position_at_circuit(conn, driver_id=1, circuit_id=3, race_date=date(2024, 5, 1))
    assert result == 6.0


def test_driver_avg_qualifying_position_at_circuit_none():
    conn = _mock_conn_scalar(None)
    result = _driver_avg_qualifying_position_at_circuit(conn, driver_id=1, circuit_id=3, race_date=date(2024, 5, 1))
    assert result is None


def test_driver_avg_position_last_n():
    conn = _mock_conn_scalar(3.5)
    result = _driver_avg_position_last_n(conn, driver_id=1, race_date=date(2024, 5, 1))
    assert result == 3.5


def test_driver_avg_position_last_n_none():
    conn = _mock_conn_scalar(None)
    result = _driver_avg_position_last_n(conn, driver_id=1, race_date=date(2024, 5, 1))
    assert result is None


def test_driver_avg_position_at_circuit():
    conn = _mock_conn_scalar(4.0)
    result = _driver_avg_position_at_circuit(conn, driver_id=1, circuit_id=3, race_date=date(2024, 5, 1))
    assert result == 4.0


def test_driver_podium_rate_at_circuit_with_results():
    conn = _mock_conn_fetchone((2, 5))  # 2 podiums in 5 races
    result = _driver_podium_rate_at_circuit(conn, driver_id=1, circuit_id=3, race_date=date(2024, 5, 1))
    assert result == pytest.approx(0.4)


def test_driver_podium_rate_at_circuit_no_races():
    conn = _mock_conn_fetchone((0, 0))
    result = _driver_podium_rate_at_circuit(conn, driver_id=1, circuit_id=3, race_date=date(2024, 5, 1))
    assert result is None


def test_is_wet_race_forecast_true():
    conn = _mock_conn_scalar(75.0)
    assert _is_wet_race_forecast(conn, race_id=1) is True


def test_is_wet_race_forecast_false():
    conn = _mock_conn_scalar(30.0)
    assert _is_wet_race_forecast(conn, race_id=1) is False


def test_is_wet_race_forecast_no_data():
    conn = _mock_conn_scalar(None)
    assert _is_wet_race_forecast(conn, race_id=1) is False


def test_driver_wet_race_avg_position():
    conn = _mock_conn_scalar(6.5)
    result = _driver_wet_race_avg_position(conn, driver_id=1, race_date=date(2024, 5, 1))
    assert result == 6.5


def test_driver_season_avg_position():
    conn = _mock_conn_scalar(2.0)
    result = _driver_season_avg_position(conn, driver_id=1, season=2024, race_date=date(2024, 5, 1))
    assert result == 2.0


def test_championship_position_found():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        (10, 100),  # driver 10 — 100 pts
        (5, 80),  # driver 5 — 80 pts
        (1, 60),  # driver 1 — 60 pts
    ]
    result = _championship_position(conn, driver_id=5, season=2024, race_date=date(2024, 5, 1))
    assert result == 2


def test_championship_position_not_scored():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        (10, 100),
        (5, 80),
    ]
    result = _championship_position(conn, driver_id=99, season=2024, race_date=date(2024, 5, 1))
    assert result is None


def test_championship_position_no_prior_races():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    result = _championship_position(conn, driver_id=1, season=2024, race_date=date(2024, 3, 1))
    assert result is None


def test_constructor_dnf_rate_last_season_with_dnfs():
    conn = MagicMock()
    # 3 DNF races out of 10 total races in previous season
    conn.execute.return_value.fetchone.return_value = (3, 10)
    result = _constructor_dnf_rate_last_season(conn, constructor_id=1, season=2023)
    assert result == pytest.approx(0.3)


def test_constructor_dnf_rate_last_season_no_dnfs():
    conn = MagicMock()
    # 0 DNF races out of 10 total
    conn.execute.return_value.fetchone.return_value = (0, 10)
    result = _constructor_dnf_rate_last_season(conn, constructor_id=1, season=2023)
    assert result == pytest.approx(0.0)


def test_constructor_dnf_rate_last_season_no_races():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (0, 0)
    result = _constructor_dnf_rate_last_season(conn, constructor_id=1, season=2023)
    assert result is None


def test_constructor_dnf_rate_last_season_all_dnfs():
    conn = MagicMock()
    # Every race had a DNF
    conn.execute.return_value.fetchone.return_value = (10, 10)
    result = _constructor_dnf_rate_last_season(conn, constructor_id=1, season=2023)
    assert result == pytest.approx(1.0)


def test_constructor_dnf_rate_last_season_none_row():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    result = _constructor_dnf_rate_last_season(conn, constructor_id=1, season=2023)
    assert result is None


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


def test_upsert_feature_executes():
    conn = MagicMock()
    _upsert_feature(conn, race_id=1, driver_id=2, feature_data={"grid_position": 5})
    conn.execute.assert_called_once()
    params = conn.execute.call_args[0][1]
    assert params["race_id"] == 1
    assert params["driver_id"] == 2
    assert '"grid_position": 5' in params["feature_data"]


# ---------------------------------------------------------------------------
# Parquet export
# ---------------------------------------------------------------------------


def test_export_parquet(tmp_path):
    df = pd.DataFrame([{"race_id": 1, "driver_id": 2, "grid_position": 5}])
    with patch("pipeline.features.builder.DATA_DIR", tmp_path):
        path = export_parquet(df, race_id=1)
    assert path.exists()
    loaded = pd.read_parquet(path)
    assert len(loaded) == 1
    assert loaded.iloc[0]["grid_position"] == 5


# ---------------------------------------------------------------------------
# Integration: build_features_for_race
# ---------------------------------------------------------------------------


def test_build_features_no_drivers():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__ = MagicMock(return_value=conn)
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    # _get_race_info returns a race, but _get_entered_drivers returns empty
    def side_effect(stmt, params=None):
        sql = str(stmt)
        result = MagicMock()
        if "FROM races r" in sql:
            result.fetchone.return_value = (1, 2024, 5, date(2024, 5, 1), 10, "street")
        elif "DISTINCT d.id" in sql:
            result.fetchall.return_value = []
        elif "SELECT dc.driver_id" in sql:
            result.fetchall.return_value = []
        return result

    conn.execute.side_effect = side_effect

    df = build_features_for_race(race_id=1, engine=engine)
    assert df.empty


def test_build_features_pre_weekend_fallback():
    """When no session data exists, driver lineup falls back to driver_contracts."""
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__ = MagicMock(return_value=conn)
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    def side_effect(stmt, params=None):
        sql = str(stmt)
        result = MagicMock()
        if "JOIN circuits c" in sql:
            # _get_race_info
            result.fetchone.return_value = (1, 2024, 5, date(2024, 5, 1), 10, "street")
        elif "DISTINCT d.id" in sql:
            # primary session-data query — empty triggers fallback
            result.fetchall.return_value = []
        elif "SELECT dc.driver_id" in sql:
            # driver_contracts fallback — returns one driver
            result.fetchall.return_value = [(1, 2)]
        elif "FROM weather_snapshots" in sql:
            result.scalar.return_value = None
        elif "FROM qualifying_results WHERE race_id" in sql:
            result.scalar.return_value = 0  # no qualifying data
        elif "GROUP BY rr.driver_id" in sql:
            # _championship_position
            result.fetchall.return_value = [(1, 50)]
        elif "COUNT(DISTINCT rr.race_id) FILTER" in sql:
            # _constructor_dnf_rate_last_season
            result.fetchone.return_value = (1, 10)
        elif "COUNT(*) FILTER" in sql:
            # _driver_podium_rate_at_circuit
            result.fetchone.return_value = (0, 5)
        else:
            result.scalar.return_value = 5.0
        return result

    conn.execute.side_effect = side_effect

    df = build_features_for_race(race_id=1, engine=engine)
    assert len(df) == 1
    assert df.iloc[0]["driver_id"] == 1
    assert df.iloc[0]["constructor_dnf_rate_last_season"] == pytest.approx(0.1)
