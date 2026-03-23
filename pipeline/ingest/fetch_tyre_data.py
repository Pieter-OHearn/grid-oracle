"""Ingest per-driver tyre compound lap counts from race sessions using FastF1.

Stores the number of laps each driver ran on each dry compound (SOFT, MEDIUM,
HARD) in the ``race_tyre_data`` table.  Used by the feature builder
to compute ``circuit_tyre_degradation_index`` and
``constructor_hard_compound_avg_position``.

Backfill ordering note
----------------------
``upsert_race`` is called with ``mark_completed=False``, so race rows created by
this script alone will have ``is_completed = FALSE``.  All feature builder SQL
queries filter ``r.is_completed = TRUE``, so those races will be invisible to
training until ``fetch_results`` has also been run.  Always run ``fetch_results``
before or after ``fetch_tyre_data`` when backfilling a season on a fresh database.
"""

import argparse
import logging

import fastf1
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

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

# Dry-weather compounds only — INTERMEDIATE and WET are excluded because they
# are driven by rain conditions, not tyre degradation characteristics, and
# would inflate avg_compounds_per_driver at wet circuits.
VALID_COMPOUNDS = {"SOFT", "MEDIUM", "HARD"}


def upsert_tyre_data(
    conn: Connection,
    race_id: int,
    driver_id: int,
    compound: str,
    lap_count: int,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO race_tyre_data (race_id, driver_id, compound, lap_count)
            VALUES (:race_id, :driver_id, :compound, :lap_count)
            ON CONFLICT (race_id, driver_id, compound) DO UPDATE
                SET lap_count = EXCLUDED.lap_count
            """
        ),
        {
            "race_id": race_id,
            "driver_id": driver_id,
            "compound": compound,
            "lap_count": lap_count,
        },
    )


def _compound_counts_from_laps(laps: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Return {driver_code: {compound: lap_count}} from a race laps DataFrame."""
    if laps is None or laps.empty or "Compound" not in laps.columns:
        return {}

    counts: dict[str, dict[str, int]] = {}
    valid = laps[laps["Compound"].isin(VALID_COMPOUNDS)]
    for (driver_code, compound), grp in valid.groupby(["Driver", "Compound"]):
        counts.setdefault(str(driver_code), {})[str(compound)] = len(grp)
    return counts


def ingest_event(season: int, round_num: int, engine: Engine) -> bool:
    """Load one race session and upsert compound lap counts into race_tyre_data.

    Returns True if any data was ingested.
    """
    logger.info("Season %d round %d: loading race session for tyre data…", season, round_num)
    try:
        session = fastf1.get_session(season, round_num, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
    except Exception as exc:
        logger.warning("Season %d round %d: failed to load race session — %s", season, round_num, exc)
        return False

    results: pd.DataFrame = session.results
    if results is None or results.empty:
        logger.warning("Season %d round %d: no results data", season, round_num)
        return False

    laps: pd.DataFrame = session.laps
    if laps is None or laps.empty:
        logger.warning("Season %d round %d: no lap data", season, round_num)
        return False

    event_name = session.event["EventName"]
    event_date = session.event["EventDate"]
    race_date = event_date.date() if hasattr(event_date, "date") else event_date

    compound_counts = _compound_counts_from_laps(laps)
    if not compound_counts:
        logger.warning("Season %d round %d: no valid compound data in laps", season, round_num)
        return False

    ingested = 0
    with engine.begin() as conn:
        circuit_id = upsert_circuit(conn, session)
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

            driver_compounds = compound_counts.get(driver_code, {})
            for compound, lap_count in driver_compounds.items():
                upsert_tyre_data(conn, race_id, driver_id, compound, lap_count)
                ingested += 1

    logger.info(
        "Season %d round %d — %s: ingested %d tyre compound rows",
        season,
        round_num,
        event_name,
        ingested,
    )
    return ingested > 0


def ingest_season(season: int, engine: Engine) -> None:
    schedule = fastf1.get_event_schedule(season, include_testing=False)
    logger.info("Season %d — %d race events found", season, len(schedule))
    for _, event in schedule.iterrows():
        ingest_event(season, int(event["RoundNumber"]), engine)
    logger.info("Season %d tyre data ingestion complete.", season)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest F1 race tyre compound lap counts.")
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
