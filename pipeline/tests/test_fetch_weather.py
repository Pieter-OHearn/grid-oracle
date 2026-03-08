"""Unit tests for pipeline.ingest.fetch_weather."""

from unittest.mock import MagicMock, patch

import pytest

from pipeline.ingest.fetch_weather import (
    fetch_and_store_weather,
    get_circuit_coordinates,
    insert_weather_snapshot,
    parse_forecast,
)

# ---------------------------------------------------------------------------
# Sample OpenWeatherMap API response for testing
# ---------------------------------------------------------------------------

SAMPLE_FORECAST = {
    "list": [
        {
            "dt": 1700000000,
            "main": {"temp": 18.5, "humidity": 72},
            "weather": [{"description": "light rain"}],
            "wind": {"speed": 4.12},
            "pop": 0.85,
        }
    ]
}


# ---------------------------------------------------------------------------
# get_circuit_coordinates
# ---------------------------------------------------------------------------


def test_get_circuit_coordinates_returns_lat_lon():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (50.4372, 5.9714)

    lat, lon = get_circuit_coordinates(conn, race_id=1)

    assert lat == 50.4372
    assert lon == 5.9714


def test_get_circuit_coordinates_race_not_found():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    with pytest.raises(ValueError, match="not found"):
        get_circuit_coordinates(conn, race_id=999)


def test_get_circuit_coordinates_missing_coordinates():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (None, None)

    with pytest.raises(ValueError, match="no coordinates"):
        get_circuit_coordinates(conn, race_id=1)


# ---------------------------------------------------------------------------
# parse_forecast
# ---------------------------------------------------------------------------


def test_parse_forecast_extracts_fields():
    result = parse_forecast(SAMPLE_FORECAST)

    assert result["rain_probability"] == 85.0
    assert result["temp_celsius"] == 18.5
    assert result["wind_speed"] == 4.12
    assert result["conditions"] == "light rain"


def test_parse_forecast_empty_list_raises():
    with pytest.raises(ValueError, match="No forecast entries"):
        parse_forecast({"list": []})


def test_parse_forecast_missing_optional_fields():
    data = {"list": [{"dt": 1700000000, "pop": 0.0}]}
    result = parse_forecast(data)

    assert result["rain_probability"] == 0.0
    assert result["temp_celsius"] is None
    assert result["wind_speed"] is None
    assert result["conditions"] == "unknown"


# ---------------------------------------------------------------------------
# insert_weather_snapshot
# ---------------------------------------------------------------------------


def test_insert_weather_snapshot_executes():
    conn = MagicMock()
    snapshot = {
        "rain_probability": 85.0,
        "temp_celsius": 18.5,
        "wind_speed": 4.12,
        "conditions": "light rain",
    }

    insert_weather_snapshot(conn, race_id=1, snapshot=snapshot)

    conn.execute.assert_called_once()
    params = conn.execute.call_args[0][1]
    assert params["race_id"] == 1
    assert params["rain_probability"] == 85.0
    assert params["temp_celsius"] == 18.5
    assert params["wind_speed"] == 4.12
    assert params["conditions"] == "light rain"
    assert "captured_at" in params


# ---------------------------------------------------------------------------
# fetch_and_store_weather (integration-style with mocks)
# ---------------------------------------------------------------------------


@patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
def test_fetch_and_store_weather_missing_api_key():
    engine = MagicMock()

    with pytest.raises(RuntimeError, match="OPENWEATHER_API_KEY"):
        fetch_and_store_weather(race_id=1, engine=engine)
