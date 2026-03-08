"""Ingest historical qualifying results for a given season using FastF1."""

import argparse
import logging
import os

import fastf1
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

UNKNOWN_COLOR = "#000000"


def get_engine() -> Engine:
    db_url = os.environ["DATABASE_URL"]
    return create_engine(db_url)


# ---------------------------------------------------------------------------
# Upsert helpers (shared pattern with fetch_results.py)
# ---------------------------------------------------------------------------

def upsert_circuit(conn, session: fastf1.core.Session) -> int:
    name = session.event["EventName"]
    country = session.event["Country"]
    city = session.event["Location"]
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
            VALUES (:season, :round, :name, :circuit_id, :date, FALSE)
            ON CONFLICT (season, round) DO UPDATE
                SET name       = EXCLUDED.name,
                    circuit_id = EXCLUDED.circuit_id,
                    date       = EXCLUDED.date
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
                SET full_name     = EXCLUDED.full_name,
                    nationality   = EXCLUDED.nationality,
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


def _interval_or_none(lap_time) -> str | None:
    """Convert a pandas Timedelta to a PostgreSQL interval string, or None."""
    if lap_time is None or (isinstance(lap_time, float) and pd.isna(lap_time)):
        return None
    try:
        if pd.isna(lap_time):
            return None
    except (TypeError, ValueError):
        pass
    total_seconds = lap_time.total_seconds()
    return f"{total_seconds} seconds"


def upsert_qualifying_result(
    conn,
    race_id: int,
    driver_id: int,
    constructor_id: int,
    q1_time,
    q2_time,
    q3_time,
    grid_position,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO qualifying_results
                (race_id, driver_id, constructor_id, q1_time, q2_time, q3_time, grid_position)
            VALUES
                (:race_id, :driver_id, :constructor_id,
                 :q1_time::interval, :q2_time::interval, :q3_time::interval,
                 :grid_position)
            ON CONFLICT (race_id, driver_id) DO UPDATE
                SET constructor_id = EXCLUDED.constructor_id,
                    q1_time        = EXCLUDED.q1_time,
                    q2_time        = EXCLUDED.q2_time,
                    q3_time        = EXCLUDED.q3_time,
                    grid_position  = EXCLUDED.grid_position
            """
        ),
        {
            "race_id": race_id,
            "driver_id": driver_id,
            "constructor_id": constructor_id,
            "q1_time": _interval_or_none(q1_time),
            "q2_time": _interval_or_none(q2_time),
            "q3_time": _interval_or_none(q3_time),
            "grid_position": int(grid_position) if pd.notna(grid_position) else None,
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
        logger.info("Round %d — %s: loading qualifying session…", round_num, event_name)

        try:
            session = fastf1.get_session(season, round_num, "Q")
            session.load(laps=False, telemetry=False, weather=False, messages=False)
        except Exception as exc:
            logger.warning("Round %d — %s: failed to load — %s", round_num, event_name, exc)
            continue

        results: pd.DataFrame = session.results
        if results is None or results.empty:
            logger.warning("Round %d — %s: no qualifying results data", round_num, event_name)
            continue

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

                q1_time = row.get("Q1")
                q2_time = row.get("Q2")
                q3_time = row.get("Q3")
                grid_position = row.get("Position")

                upsert_qualifying_result(
                    conn,
                    race_id,
                    driver_id,
                    constructor_id,
                    q1_time,
                    q2_time,
                    q3_time,
                    grid_position,
                )

        logger.info(
            "Round %d — %s: ingested %d qualifying results", round_num, event_name, len(results)
        )

    logger.info("Season %d qualifying ingestion complete.", season)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest F1 qualifying results for a season.")
    parser.add_argument("--season", type=int, required=True, help="Season year, e.g. 2023")
    args = parser.parse_args()

    engine = get_engine()
    ingest_season(args.season, engine)


if __name__ == "__main__":
    main()
