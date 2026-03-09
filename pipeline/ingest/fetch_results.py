"""Ingest historical race results for a given season using FastF1."""

import argparse
import logging

import fastf1
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.ingest.upsert_helpers import (
    get_engine,
    upsert_circuit,
    upsert_constructor,
    upsert_driver,
    upsert_driver_contract,
    upsert_race,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
for _noisy in ("fastf1", "req", "core", "logger", "_api"):
    logging.getLogger(_noisy).setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)


def upsert_race_result(
    conn,
    race_id: int,
    driver_id: int,
    constructor_id: int,
    grid_position,
    finish_position,
    points: float,
    status: str,
    fastest_lap: bool,
    is_wet_race: bool,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO race_results
                (race_id, driver_id, constructor_id, grid_position, finish_position,
                 points, status, fastest_lap, is_wet_race)
            VALUES
                (:race_id, :driver_id, :constructor_id, :grid_position, :finish_position,
                 :points, :status, :fastest_lap, :is_wet_race)
            ON CONFLICT (race_id, driver_id) DO UPDATE
                SET constructor_id   = EXCLUDED.constructor_id,
                    grid_position    = EXCLUDED.grid_position,
                    finish_position  = EXCLUDED.finish_position,
                    points           = EXCLUDED.points,
                    status           = EXCLUDED.status,
                    fastest_lap      = EXCLUDED.fastest_lap,
                    is_wet_race      = EXCLUDED.is_wet_race
            """
        ),
        {
            "race_id": race_id,
            "driver_id": driver_id,
            "constructor_id": constructor_id,
            "grid_position": int(grid_position) if pd.notna(grid_position) else None,
            "finish_position": int(finish_position) if pd.notna(finish_position) else None,
            "points": float(points) if pd.notna(points) else 0.0,
            "status": status,
            "fastest_lap": fastest_lap,
            "is_wet_race": is_wet_race,
        },
    )


# ---------------------------------------------------------------------------
# Main ingestion logic
# ---------------------------------------------------------------------------


def ingest_event(season: int, round_num: int, engine: Engine) -> bool:
    """Ingest race results for a single event.

    Returns True if data was ingested, False if skipped (no data available).
    """
    logger.info("Season %d round %d: loading race session…", season, round_num)

    try:
        session = fastf1.get_session(season, round_num, "R")
        session.load(laps=False, telemetry=False, weather=True, messages=False)
    except Exception as exc:
        logger.warning("Season %d round %d: failed to load — %s", season, round_num, exc)
        return False

    event_name = session.event["EventName"]
    results: pd.DataFrame = session.results
    if results is None or results.empty:
        logger.warning("Round %d — %s: no results data", round_num, event_name)
        return False

    # Determine if the race was wet (any lap recorded as wet)
    is_wet_race = False
    try:
        weather_data = session.weather_data
        if weather_data is not None and not weather_data.empty and "Rainfall" in weather_data.columns:
            is_wet_race = bool(weather_data["Rainfall"].any())
    except Exception:
        pass

    event_date = session.event["EventDate"]
    race_date = event_date.date() if hasattr(event_date, "date") else event_date

    with engine.begin() as conn:
        circuit_id = upsert_circuit(conn, session)
        race_id = upsert_race(conn, season, round_num, event_name, circuit_id, race_date, mark_completed=True)

        for _, row in results.iterrows():
            driver_code = str(row.get("Abbreviation", ""))[:3]
            if not driver_code:
                continue

            full_name = str(row.get("FullName", driver_code))
            nationality = str(row.get("CountryCode", ""))
            constructor_name = str(row.get("TeamName", "Unknown"))
            constructor_nationality = str(row.get("TeamNationality", ""))

            driver_id = upsert_driver(conn, driver_code, full_name, nationality)
            constructor_id = upsert_constructor(conn, constructor_name, constructor_nationality)
            upsert_driver_contract(conn, driver_id, constructor_id, season)

            upsert_race_result(
                conn,
                race_id,
                driver_id,
                constructor_id,
                row.get("GridPosition"),
                row.get("Position"),
                row.get("Points", 0),
                str(row.get("Status", "Unknown")),
                bool(row.get("FastestLap", False)),
                is_wet_race,
            )

    logger.info("Round %d — %s: ingested %d driver results", round_num, event_name, len(results))
    return True


def ingest_season(season: int, engine: Engine) -> None:
    schedule = fastf1.get_event_schedule(season, include_testing=False)
    logger.info("Season %d — %d race events found", season, len(schedule))

    for _, event in schedule.iterrows():
        round_num = int(event["RoundNumber"])
        ingest_event(season, round_num, engine)

    logger.info("Season %d ingestion complete.", season)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest F1 race results.")
    parser.add_argument("--season", type=int, required=True, help="Season year, e.g. 2023")
    parser.add_argument("--round", type=int, default=None, help="Single round number")
    args = parser.parse_args()

    engine = get_engine()
    if args.round is not None:
        ingest_event(args.season, args.round, engine)
    else:
        ingest_season(args.season, engine)


if __name__ == "__main__":
    main()
