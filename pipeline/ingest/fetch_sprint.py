"""Ingest sprint race results for a given season using FastF1."""

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


def upsert_sprint_result(
    conn,
    race_id: int,
    driver_id: int,
    sprint_position,
    status: str,
    points: float,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO sprint_results (race_id, driver_id, sprint_position, status, points)
            VALUES (:race_id, :driver_id, :sprint_position, :status, :points)
            ON CONFLICT (race_id, driver_id) DO UPDATE
                SET sprint_position = EXCLUDED.sprint_position,
                    status          = EXCLUDED.status,
                    points          = EXCLUDED.points
            """
        ),
        {
            "race_id": race_id,
            "driver_id": driver_id,
            "sprint_position": int(sprint_position) if pd.notna(sprint_position) else None,
            "status": status,
            "points": float(points) if pd.notna(points) else 0.0,
        },
    )


# ---------------------------------------------------------------------------
# Main ingestion logic
# ---------------------------------------------------------------------------


def ingest_event(season: int, round_num: int, engine: Engine) -> bool:
    """Ingest sprint race results for a single event.

    Returns True if data was ingested, False if skipped (no data available).
    """
    logger.info("Season %d round %d: loading sprint session…", season, round_num)

    try:
        session = fastf1.get_session(season, round_num, "Sprint")
        session.load(laps=False, telemetry=False, weather=False, messages=False)
    except Exception as exc:
        logger.warning("Season %d round %d: failed to load sprint session — %s", season, round_num, exc)
        return False

    event_name = session.event["EventName"]
    results: pd.DataFrame = session.results
    if results is None or results.empty:
        logger.warning("Round %d — %s: no sprint results data", round_num, event_name)
        return False

    event_date = session.event["EventDate"]
    race_date = event_date.date() if hasattr(event_date, "date") else event_date

    with engine.begin() as conn:
        circuit_id = upsert_circuit(conn, session)
        # mark_completed=False: sprint ingest must not downgrade an existing TRUE value
        race_id = upsert_race(conn, season, round_num, event_name, circuit_id, race_date, mark_completed=False)

        for _, row in results.iterrows():
            driver_code = str(row.get("Abbreviation", ""))[:3]
            if not driver_code:
                continue

            full_name = str(row.get("FullName", driver_code))
            nationality = str(row.get("CountryCode", ""))
            constructor_name = str(row.get("TeamName", "Unknown"))
            constructor_nationality = str(row.get("TeamNationality", ""))
            driver_number_raw = row.get("DriverNumber")
            driver_number = int(driver_number_raw) if driver_number_raw is not None else None

            driver_id = upsert_driver(conn, driver_code, full_name, nationality, driver_number)
            constructor_id = upsert_constructor(conn, constructor_name, constructor_nationality)
            upsert_driver_contract(conn, driver_id, constructor_id, season, round_num)

            upsert_sprint_result(
                conn,
                race_id,
                driver_id,
                row.get("Position"),
                str(row.get("Status", "Unknown")),
                row.get("Points", 0),
            )

    logger.info("Round %d — %s: ingested %d sprint results", round_num, event_name, len(results))
    return True


def ingest_season(season: int, engine: Engine) -> None:
    schedule = fastf1.get_event_schedule(season, include_testing=False)
    logger.info("Season %d — %d race events found", season, len(schedule))

    for _, event in schedule.iterrows():
        event_format = str(event.get("EventFormat", ""))
        if "sprint" not in event_format.lower():
            continue
        round_num = int(event["RoundNumber"])
        ingest_event(season, round_num, engine)

    logger.info("Season %d sprint ingestion complete.", season)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest F1 sprint race results.")
    parser.add_argument("--season", type=int, required=True, help="Season year, e.g. 2026")
    parser.add_argument("--round", type=int, default=None, help="Single round number")
    args = parser.parse_args()

    engine = get_engine()
    if args.round is not None:
        ingest_event(args.season, args.round, engine)
    else:
        ingest_season(args.season, engine)


if __name__ == "__main__":
    main()
