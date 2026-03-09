"""Unit tests for pipeline.ingest.fetch_weather."""

from unittest.mock import MagicMock, patch

import pytest

from pipeline.ingest.fetch_weather import (
    fetch_and_store_weather,
    geocode_circuit,
    get_race_circuit_info,
    insert_weather_snapshot,
    parse_forecast,
    resolve_coordinates,
    update_circuit_coordinates,
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
# geocode_circuit
# ---------------------------------------------------------------------------


@patch("pipeline.ingest.fetch_weather.requests.get")
def test_geocode_circuit_returns_lat_lon(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"lat": 34.8431, "lon": 136.5407}]
    mock_get.return_value = mock_resp

    lat, lon = geocode_circuit("Suzuka", "Japan", "fake-key")

    assert lat == 34.8431
    assert lon == 136.5407
    mock_get.assert_called_once()
    call_params = mock_get.call_args[1]["params"]
    assert call_params["q"] == "Suzuka,Japan"


@patch("pipeline.ingest.fetch_weather.requests.get")
def test_geocode_circuit_empty_results_raises(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = []
    mock_get.return_value = mock_resp

    with pytest.raises(ValueError, match="no results"):
        geocode_circuit("Nowhere", "Noland", "fake-key")


# ---------------------------------------------------------------------------
# get_race_circuit_info
# ---------------------------------------------------------------------------


def test_get_race_circuit_info_returns_full_info():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (5, 50.4372, 5.9714, "Spa-Francorchamps", "Belgium")

    info = get_race_circuit_info(conn, race_id=1)

    assert info["circuit_id"] == 5
    assert info["latitude"] == 50.4372
    assert info["longitude"] == 5.9714
    assert info["city"] == "Spa-Francorchamps"
    assert info["country"] == "Belgium"


def test_get_race_circuit_info_race_not_found():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    with pytest.raises(ValueError, match="not found"):
        get_race_circuit_info(conn, race_id=999)


def test_get_race_circuit_info_null_coordinates():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (5, None, None, "Suzuka", "Japan")

    info = get_race_circuit_info(conn, race_id=1)

    assert info["circuit_id"] == 5
    assert info["latitude"] is None
    assert info["longitude"] is None
    assert info["city"] == "Suzuka"


# ---------------------------------------------------------------------------
# update_circuit_coordinates
# ---------------------------------------------------------------------------


def test_update_circuit_coordinates_executes():
    conn = MagicMock()

    update_circuit_coordinates(conn, circuit_id=5, lat=34.8431, lon=136.5407)

    conn.execute.assert_called_once()
    params = conn.execute.call_args[0][1]
    assert params["circuit_id"] == 5
    assert params["lat"] == 34.8431
    assert params["lon"] == 136.5407


# ---------------------------------------------------------------------------
# resolve_coordinates
# ---------------------------------------------------------------------------


def test_resolve_coordinates_uses_existing():
    conn = MagicMock()
    info = {"circuit_id": 5, "latitude": 50.4372, "longitude": 5.9714, "city": "Spa", "country": "Belgium"}

    lat, lon = resolve_coordinates(info, "fake-key", conn)

    assert lat == 50.4372
    assert lon == 5.9714
    conn.execute.assert_not_called()


@patch("pipeline.ingest.fetch_weather.geocode_circuit")
def test_resolve_coordinates_geocodes_when_missing(mock_geocode):
    conn = MagicMock()
    mock_geocode.return_value = (34.8431, 136.5407)
    info = {"circuit_id": 5, "latitude": None, "longitude": None, "city": "Suzuka", "country": "Japan"}

    lat, lon = resolve_coordinates(info, "fake-key", conn)

    assert lat == 34.8431
    assert lon == 136.5407
    mock_geocode.assert_called_once_with("Suzuka", "Japan", "fake-key")
    conn.execute.assert_called_once()  # update_circuit_coordinates was called


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
# fetch_and_store_weather
# ---------------------------------------------------------------------------


@patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
def test_fetch_and_store_weather_missing_api_key():
    engine = MagicMock()

    with pytest.raises(RuntimeError, match="OPENWEATHER_API_KEY"):
        fetch_and_store_weather(race_id=1, engine=engine)
