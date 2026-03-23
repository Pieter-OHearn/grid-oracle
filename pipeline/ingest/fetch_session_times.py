"""Ingest historical qualifying sector times and FP2 pace using FastF1.

Qualifying sector times and practice pace from previous seasons at a circuit
are strong pre-weekend signals of driver/constructor performance.  This script
loads laps from Qualifying ('Q') and Free Practice 2 ('FP2') sessions and
stores the per-driver best times in the ``session_times`` table.

Backfill ordering note
----------------------
``upsert_race`` is called with ``mark_completed=False``, which means race rows
created by this script alone will have ``is_completed = FALSE``.  All feature
builder SQL queries filter ``r.is_completed = TRUE``, so those races will be
invisible to training until ``fetch_results`` (which sets ``is_completed = TRUE``)
has also been run for that season.  Always run ``fetch_results`` before or after
``fetch_session_times`` when backfilling a season on a fresh database.
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


def _timedelta_to_ms(td: pd.Timedelta | None) -> int | None:
    """Convert a pandas Timedelta to milliseconds, or None for missing data."""
    if td is None:
        return None
    try:
        if pd.isna(td):
            return None
    except (TypeError, ValueError):
        pass
    return int(float(td.total_seconds()) * 1000)


def _to_py_int(v) -> int | None:
    """Coerce a value to Python int, returning None for missing."""
    return None if v is None or (hasattr(v, "__class__") and v != v) else int(v)


def upsert_session_time(
    conn: Connection,
    race_id: int,
    driver_id: int,
    session_type: str,
    best_lap_ms: int | None,
    sector1_ms: int | None,
    sector2_ms: int | None,
    sector3_ms: int | None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO session_times
                (race_id, driver_id, session_type, best_lap_ms,
                 sector1_ms, sector2_ms, sector3_ms)
            VALUES
                (:race_id, :driver_id, :session_type, :best_lap_ms,
                 :sector1_ms, :sector2_ms, :sector3_ms)
            ON CONFLICT (race_id, driver_id, session_type) DO UPDATE
                SET best_lap_ms = EXCLUDED.best_lap_ms,
                    sector1_ms  = EXCLUDED.sector1_ms,
                    sector2_ms  = EXCLUDED.sector2_ms,
                    sector3_ms  = EXCLUDED.sector3_ms
            """
        ),
        {
            "race_id": race_id,
            "driver_id": driver_id,
            "session_type": session_type,
            "best_lap_ms": _to_py_int(best_lap_ms),
            "sector1_ms": _to_py_int(sector1_ms),
            "sector2_ms": _to_py_int(sector2_ms),
            "sector3_ms": _to_py_int(sector3_ms),
        },
    )


def _best_per_driver_from_laps(laps: pd.DataFrame, session_type: str) -> pd.DataFrame:
    """Return a DataFrame with best lap/sector times per driver.

    For qualifying: independent per-sector minimums across all laps (theoretical
    best — each sector may come from a different lap).
    For FP2: min full lap time only (sector columns left as None).

    Returns columns: Driver, best_lap_ms, sector1_ms, sector2_ms, sector3_ms
    """
    if laps is None or laps.empty:
        return pd.DataFrame(columns=["Driver", "best_lap_ms", "sector1_ms", "sector2_ms", "sector3_ms"])

    rows = []
    for driver_code, grp in laps.groupby("Driver"):
        best_lap_ms = None
        sector1_ms = None
        sector2_ms = None
        sector3_ms = None

        if "LapTime" in grp.columns:
            valid_laps = grp["LapTime"].dropna()
            if not valid_laps.empty:
                best_lap_ms = _timedelta_to_ms(valid_laps.min())

        if session_type == "Q":
            if "Sector1Time" in grp.columns:
                valid = grp["Sector1Time"].dropna()
                if not valid.empty:
                    sector1_ms = _timedelta_to_ms(valid.min())
            if "Sector2Time" in grp.columns:
                valid = grp["Sector2Time"].dropna()
                if not valid.empty:
                    sector2_ms = _timedelta_to_ms(valid.min())
            if "Sector3Time" in grp.columns:
                valid = grp["Sector3Time"].dropna()
                if not valid.empty:
                    sector3_ms = _timedelta_to_ms(valid.min())

        rows.append(
            {
                "Driver": driver_code,
                "best_lap_ms": best_lap_ms,
                "sector1_ms": sector1_ms,
                "sector2_ms": sector2_ms,
                "sector3_ms": sector3_ms,
            }
        )

    return pd.DataFrame(rows)


def _ingest_session(
    season: int,
    round_num: int,
    session_identifier: str,
    engine: Engine,
) -> bool:
    """Load one session and upsert per-driver best times into session_times.

    Returns True if data was ingested.
    """
    logger.info("Season %d round %d: loading %s session…", season, round_num, session_identifier)
    try:
        session = fastf1.get_session(season, round_num, session_identifier)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
    except Exception as exc:
        logger.warning(
            "Season %d round %d %s: failed to load — %s",
            season,
            round_num,
            session_identifier,
            exc,
        )
        return False

    results: pd.DataFrame = session.results
    if results is None or results.empty:
        logger.warning("Season %d round %d %s: no results data", season, round_num, session_identifier)
        return False

    laps: pd.DataFrame = session.laps
    if laps is None or laps.empty:
        logger.warning("Season %d round %d %s: no lap data", season, round_num, session_identifier)
        return False

    event_name = session.event["EventName"]
    event_date = session.event["EventDate"]
    race_date = event_date.date() if hasattr(event_date, "date") else event_date

    # Build per-driver best times from laps
    timing = _best_per_driver_from_laps(laps, session_identifier)
    if timing.empty:
        logger.warning("Season %d round %d %s: no usable lap times", season, round_num, session_identifier)
        return False

    timing_by_driver = timing.set_index("Driver")
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

            if driver_code not in timing_by_driver.index:
                continue

            t = timing_by_driver.loc[driver_code]
            upsert_session_time(
                conn,
                race_id,
                driver_id,
                session_identifier,
                t.get("best_lap_ms"),
                t.get("sector1_ms"),
                t.get("sector2_ms"),
                t.get("sector3_ms"),
            )
            ingested += 1

    logger.info(
        "Season %d round %d %s — %s: ingested %d driver session times",
        season,
        round_num,
        session_identifier,
        event_name,
        ingested,
    )
    return ingested > 0


def ingest_event(season: int, round_num: int, engine: Engine) -> bool:
    """Ingest qualifying sector times and FP2 pace for one event.

    Returns True if at least one session was ingested.
    """
    q_ok = _ingest_session(season, round_num, "Q", engine)
    fp2_ok = _ingest_session(season, round_num, "FP2", engine)
    return q_ok or fp2_ok


def ingest_season(season: int, engine: Engine) -> None:
    schedule = fastf1.get_event_schedule(season, include_testing=False)
    logger.info("Season %d — %d race events found", season, len(schedule))
    for _, event in schedule.iterrows():
        ingest_event(season, int(event["RoundNumber"]), engine)
    logger.info("Season %d session-times ingestion complete.", season)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest F1 qualifying sector times and FP2 pace.")
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
