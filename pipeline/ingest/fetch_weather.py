"""Fetch weather forecast for an upcoming race and store a snapshot."""

import argparse
import logging
import os
from datetime import datetime, timezone

import requests
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.ingest.upsert_helpers import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
OPENWEATHER_GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------


def geocode_circuit(city: str, country: str, api_key: str) -> tuple[float, float]:
    """Resolve a city + country to (lat, lon) via OpenWeatherMap geocoding API."""
    resp = requests.get(
        OPENWEATHER_GEOCODE_URL,
        params={"q": f"{city},{country}", "limit": 1, "appid": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json()

    if not results:
        raise ValueError(f"Geocoding returned no results for '{city}, {country}'")

    return float(results[0]["lat"]), float(results[0]["lon"])


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def get_race_circuit_info(conn, race_id: int) -> dict:
    """Look up circuit details for a given race, including coordinates and city/country."""
    row = conn.execute(
        text(
            """
            SELECT c.id, c.latitude, c.longitude, c.city, c.country
            FROM races r
            JOIN circuits c ON r.circuit_id = c.id
            WHERE r.id = :race_id
            """
        ),
        {"race_id": race_id},
    ).fetchone()

    if row is None:
        raise ValueError(f"Race with id {race_id} not found")

    return {
        "circuit_id": row[0],
        "latitude": float(row[1]) if row[1] is not None else None,
        "longitude": float(row[2]) if row[2] is not None else None,
        "city": row[3],
        "country": row[4],
    }


def update_circuit_coordinates(conn, circuit_id: int, lat: float, lon: float) -> None:
    """Store geocoded coordinates on the circuit row for future lookups."""
    conn.execute(
        text(
            """
            UPDATE circuits
            SET latitude = :lat, longitude = :lon
            WHERE id = :circuit_id
            """
        ),
        {"circuit_id": circuit_id, "lat": lat, "lon": lon},
    )


def insert_weather_snapshot(conn, race_id: int, snapshot: dict) -> None:
    """Insert a weather snapshot row.

    No upsert — multiple snapshots per race are allowed by design so that
    forecasts captured at different times can be compared.
    """
    conn.execute(
        text(
            """
            INSERT INTO weather_snapshots
                (race_id, captured_at, rain_probability, temp_celsius, wind_speed, conditions)
            VALUES
                (:race_id, :captured_at, :rain_probability, :temp_celsius, :wind_speed, :conditions)
            """
        ),
        {
            "race_id": race_id,
            "captured_at": datetime.now(timezone.utc),
            "rain_probability": snapshot["rain_probability"],
            "temp_celsius": snapshot["temp_celsius"],
            "wind_speed": snapshot["wind_speed"],
            "conditions": snapshot["conditions"],
        },
    )


# ---------------------------------------------------------------------------
# OpenWeatherMap API helpers
# ---------------------------------------------------------------------------


def fetch_forecast(lat: float, lon: float, api_key: str) -> dict:
    """Call the OpenWeatherMap 5-day / 3-hour forecast API."""
    resp = requests.get(
        OPENWEATHER_FORECAST_URL,
        params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def parse_forecast(data: dict) -> dict:
    """Extract a weather summary from the first forecast entry.

    Returns a dict with rain_probability, temp_celsius, wind_speed, conditions.
    """
    forecasts = data.get("list", [])
    if not forecasts:
        raise ValueError("No forecast entries in API response")

    entry = forecasts[0]

    # pop (probability of precipitation) is 0.0-1.0; convert to 0-100 percentage
    rain_probability = round(entry.get("pop", 0.0) * 100, 2)

    main = entry.get("main", {})
    temp_celsius = main.get("temp")

    wind = entry.get("wind", {})
    wind_speed = wind.get("speed")

    weather_list = entry.get("weather", [])
    conditions = weather_list[0].get("description", "unknown") if weather_list else "unknown"

    return {
        "rain_probability": rain_probability,
        "temp_celsius": round(temp_celsius, 2) if temp_celsius is not None else None,
        "wind_speed": round(wind_speed, 2) if wind_speed is not None else None,
        "conditions": conditions,
    }


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------


def resolve_coordinates(circuit_info: dict, api_key: str, conn) -> tuple[float, float]:
    """Return (lat, lon) for a circuit, geocoding and persisting if missing."""
    lat, lon = circuit_info["latitude"], circuit_info["longitude"]

    if lat is not None and lon is not None:
        return lat, lon

    city = circuit_info["city"]
    country = circuit_info["country"]
    logger.info(
        "Circuit %d has no coordinates — geocoding '%s, %s'…",
        circuit_info["circuit_id"],
        city,
        country,
    )

    lat, lon = geocode_circuit(city, country, api_key)
    update_circuit_coordinates(conn, circuit_info["circuit_id"], lat, lon)
    logger.info("Circuit %d coordinates saved: (%.4f, %.4f)", circuit_info["circuit_id"], lat, lon)

    return lat, lon


def fetch_and_store_weather(race_id: int, engine: Engine) -> None:
    """Look up circuit coordinates, fetch forecast, and store a snapshot."""
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY environment variable is not set")

    with engine.begin() as conn:
        circuit_info = get_race_circuit_info(conn, race_id)
        lat, lon = resolve_coordinates(circuit_info, api_key, conn)

    logger.info("Race %d — circuit at (%.4f, %.4f), fetching forecast…", race_id, lat, lon)

    data = fetch_forecast(lat, lon, api_key)
    snapshot = parse_forecast(data)

    with engine.begin() as conn:
        insert_weather_snapshot(conn, race_id, snapshot)

    logger.info(
        "Race %d — weather snapshot stored: %.0f%% rain, %.1f°C, %s",
        race_id,
        snapshot["rain_probability"],
        snapshot["temp_celsius"] or 0,
        snapshot["conditions"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch weather forecast for an upcoming race.")
    parser.add_argument("--race_id", type=int, required=True, help="Database ID of the race")
    args = parser.parse_args()

    engine = get_engine()
    fetch_and_store_weather(args.race_id, engine)


if __name__ == "__main__":
    main()
