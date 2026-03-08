"""Ingest historical race results for a given season using FastF1."""

import argparse
import logging
import os

import fastf1
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Placeholder hex colour when a constructor has no known colour.
UNKNOWN_COLOR = "#000000"


def get_engine() -> Engine:
    db_url = os.environ["DATABASE_URL"]
    return create_engine(db_url)


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def upsert_circuit(conn, circuit_info: fastf1.core.Session) -> int:
    """Insert circuit if absent; return its id."""
    name = circuit_info.event["EventName"]
    country = circuit_info.event["Country"]
    city = circuit_info.event["Location"]
    # FastF1 doesn't expose circuit_type / total_laps / length_km directly;
    # use sensible defaults so the row can be enriched later.
    row = conn.execute(
        text(
            """
            INSERT INTO circuits (name, country, city, circuit_type, total_laps, length_km)
            VALUES (:name, :country, :city, 'unknown', 0, 0)
            ON CONFLICT DO NOTHING
            RETURNING id
            """
        ),
        {"name": name, "country": country, "city": city},
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(
        text("SELECT id FROM circuits WHERE name = :name"), {"name": name}
    ).scalar_one()


def upsert_race(conn, season: int, round_num: int, name: str, circuit_id: int, date) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO races (season, round, name, circuit_id, date, is_completed)
            VALUES (:season, :round, :name, :circuit_id, :date, TRUE)
            ON CONFLICT (season, round) DO UPDATE
                SET name        = EXCLUDED.name,
                    circuit_id  = EXCLUDED.circuit_id,
                    date        = EXCLUDED.date,
                    is_completed = TRUE
            RETURNING id
            """
        ),
        {
            "season": season,
            "round": round_num,
            "name": name,
            "circuit_id": circuit_id,
            "date": date,
        },
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(
        text("SELECT id FROM races WHERE season = :s AND round = :r"),
        {"s": season, "r": round_num},
    ).scalar_one()


def upsert_driver(conn, code: str, full_name: str, nationality: str, dob) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO drivers (code, full_name, nationality, date_of_birth)
            VALUES (:code, :full_name, :nationality, :dob)
            ON CONFLICT (code) DO UPDATE
                SET full_name   = EXCLUDED.full_name,
                    nationality = EXCLUDED.nationality,
                    date_of_birth = EXCLUDED.date_of_birth
            RETURNING id
            """
        ),
        {"code": code, "full_name": full_name, "nationality": nationality, "dob": dob},
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(
        text("SELECT id FROM drivers WHERE code = :code"), {"code": code}
    ).scalar_one()


def upsert_constructor(conn, name: str, nationality: str) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO constructors (name, nationality, color_hex)
            VALUES (:name, :nationality, :color)
            ON CONFLICT DO NOTHING
            RETURNING id
            """
        ),
        {"name": name, "nationality": nationality, "color": UNKNOWN_COLOR},
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(
        text("SELECT id FROM constructors WHERE name = :name"), {"name": name}
    ).scalar_one()


def upsert_driver_contract(conn, driver_id: int, constructor_id: int, season: int) -> None:
    conn.execute(
        text(
            """
            INSERT INTO driver_contracts (driver_id, constructor_id, season)
            VALUES (:driver_id, :constructor_id, :season)
            ON CONFLICT (driver_id, season) DO UPDATE
                SET constructor_id = EXCLUDED.constructor_id
            """
        ),
        {"driver_id": driver_id, "constructor_id": constructor_id, "season": season},
    )


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

def ingest_season(season: int, engine: Engine) -> None:
    schedule = fastf1.get_event_schedule(season, include_testing=False)
    logger.info("Season %d — %d race events found", season, len(schedule))

    for _, event in schedule.iterrows():
        round_num = int(event["RoundNumber"])
        event_name = event["EventName"]
        logger.info("Round %d — %s: loading session…", round_num, event_name)

        try:
            session = fastf1.get_session(season, round_num, "R")
            session.load(laps=False, telemetry=False, weather=True, messages=False)
        except Exception as exc:
            logger.warning("Round %d — %s: failed to load — %s", round_num, event_name, exc)
            continue

        results: pd.DataFrame = session.results
        if results is None or results.empty:
            logger.warning("Round %d — %s: no results data", round_num, event_name)
            continue

        # Determine if the race was wet (any lap recorded as wet)
        is_wet_race = False
        try:
            weather_data = session.weather_data
            if weather_data is not None and not weather_data.empty and "Rainfall" in weather_data.columns:
                is_wet_race = bool(weather_data["Rainfall"].any())
        except Exception:
            pass

        race_date = event["EventDate"].date() if hasattr(event["EventDate"], "date") else event["EventDate"]

        with engine.begin() as conn:
            circuit_id = upsert_circuit(conn, session)
            race_id = upsert_race(conn, season, round_num, event_name, circuit_id, race_date)

            for _, row in results.iterrows():
                driver_code = str(row.get("Abbreviation", ""))[:3]
                if not driver_code:
                    continue

                full_name = str(row.get("FullName", driver_code))
                nationality = str(row.get("CountryCode", ""))
                dob = row.get("DateOfBirth")
                if pd.isna(dob) if isinstance(dob, float) else dob is None:
                    dob = "1900-01-01"

                constructor_name = str(row.get("TeamName", "Unknown"))
                constructor_nationality = str(row.get("TeamNationality", ""))

                driver_id = upsert_driver(conn, driver_code, full_name, nationality, dob)
                constructor_id = upsert_constructor(conn, constructor_name, constructor_nationality)
                upsert_driver_contract(conn, driver_id, constructor_id, season)

                grid_pos = row.get("GridPosition")
                finish_pos = row.get("Position")
                points = row.get("Points", 0)
                status = str(row.get("Status", "Unknown"))
                fastest_lap = bool(row.get("FastestLap", False))

                upsert_race_result(
                    conn,
                    race_id,
                    driver_id,
                    constructor_id,
                    grid_pos,
                    finish_pos,
                    points,
                    status,
                    fastest_lap,
                    is_wet_race,
                )

        logger.info("Round %d — %s: ingested %d driver results", round_num, event_name, len(results))

    logger.info("Season %d ingestion complete.", season)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest F1 race results for a season.")
    parser.add_argument("--season", type=int, required=True, help="Season year, e.g. 2023")
    args = parser.parse_args()

    engine = get_engine()
    ingest_season(args.season, engine)


if __name__ == "__main__":
    main()
