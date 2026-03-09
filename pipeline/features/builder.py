"""Feature engineering module — generates one feature row per driver per race."""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import Connection, text
from sqlalchemy.engine import Engine

from pipeline.ingest.upsert_helpers import get_engine

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# SQL helpers — each returns a single feature value or a dict of features
# ---------------------------------------------------------------------------


def _get_race_info(conn: Connection, race_id: int) -> dict:
    """Return race metadata needed for feature building."""
    row = conn.execute(
        text(
            """
            SELECT r.id, r.season, r.round, r.date, r.circuit_id,
                   c.circuit_type
            FROM races r
            JOIN circuits c ON c.id = r.circuit_id
            WHERE r.id = :race_id
            """
        ),
        {"race_id": race_id},
    ).fetchone()
    if row is None:
        raise ValueError(f"Race {race_id} not found")
    return {
        "race_id": row[0],
        "season": row[1],
        "round": row[2],
        "date": row[3],
        "circuit_id": row[4],
        "circuit_type": row[5],
    }


def _get_entered_drivers(conn: Connection, race_id: int) -> list[dict]:
    """Return drivers entered in the race (from qualifying or race results)."""
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT d.id AS driver_id, dc.constructor_id
            FROM (
                SELECT driver_id, constructor_id FROM qualifying_results WHERE race_id = :rid
                UNION
                SELECT driver_id, constructor_id FROM race_results WHERE race_id = :rid
            ) sub
            JOIN drivers d ON d.id = sub.driver_id
            JOIN driver_contracts dc ON dc.driver_id = d.id
                AND dc.season = (SELECT season FROM races WHERE id = :rid)
            """
        ),
        {"rid": race_id},
    ).fetchall()
    return [{"driver_id": r[0], "constructor_id": r[1]} for r in rows]


def _grid_position(conn: Connection, race_id: int, driver_id: int) -> int | None:
    """Grid position from qualifying results."""
    return conn.execute(
        text("SELECT grid_position FROM qualifying_results WHERE race_id = :rid AND driver_id = :did"),
        {"rid": race_id, "did": driver_id},
    ).scalar()


def _driver_avg_position_last_n(conn: Connection, driver_id: int, race_date: object, n: int = 3) -> float | None:
    """Average finish position across the driver's last N completed races."""
    val = conn.execute(
        text(
            """
            SELECT AVG(sub.finish_position)
            FROM (
                SELECT rr.finish_position
                FROM race_results rr
                JOIN races r ON r.id = rr.race_id
                WHERE rr.driver_id = :did
                  AND rr.finish_position IS NOT NULL
                  AND r.date < :race_date
                  AND r.is_completed = TRUE
                ORDER BY r.date DESC
                LIMIT :n
            ) sub
            """
        ),
        {"did": driver_id, "race_date": race_date, "n": n},
    ).scalar()
    return float(val) if val is not None else None


def _driver_avg_position_at_circuit(
    conn: Connection, driver_id: int, circuit_id: int, race_date: object
) -> float | None:
    val = conn.execute(
        text(
            """
            SELECT AVG(rr.finish_position)
            FROM race_results rr
            JOIN races r ON r.id = rr.race_id
            WHERE rr.driver_id = :did
              AND r.circuit_id = :cid
              AND rr.finish_position IS NOT NULL
              AND r.date < :race_date
              AND r.is_completed = TRUE
            """
        ),
        {"did": driver_id, "cid": circuit_id, "race_date": race_date},
    ).scalar()
    return float(val) if val is not None else None


def _driver_podium_rate_at_circuit(
    conn: Connection, driver_id: int, circuit_id: int, race_date: object
) -> float | None:
    row = conn.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE rr.finish_position <= 3) AS podiums,
                COUNT(*) AS total
            FROM race_results rr
            JOIN races r ON r.id = rr.race_id
            WHERE rr.driver_id = :did
              AND r.circuit_id = :cid
              AND rr.finish_position IS NOT NULL
              AND r.date < :race_date
              AND r.is_completed = TRUE
            """
        ),
        {"did": driver_id, "cid": circuit_id, "race_date": race_date},
    ).fetchone()
    if row is None or row[1] == 0:
        return None
    return float(row[0]) / float(row[1])


def _constructor_avg_position_last_n(
    conn: Connection, constructor_id: int, race_date: object, n: int = 3
) -> float | None:
    val = conn.execute(
        text(
            """
            SELECT AVG(sub.finish_position)
            FROM (
                SELECT rr.finish_position
                FROM race_results rr
                JOIN races r ON r.id = rr.race_id
                WHERE rr.constructor_id = :cid
                  AND rr.finish_position IS NOT NULL
                  AND r.date < :race_date
                  AND r.is_completed = TRUE
                ORDER BY r.date DESC
                LIMIT :n
            ) sub
            """
        ),
        {"cid": constructor_id, "race_date": race_date, "n": n},
    ).scalar()
    return float(val) if val is not None else None


def _constructor_avg_position_at_circuit(
    conn: Connection, constructor_id: int, circuit_id: int, race_date: object
) -> float | None:
    val = conn.execute(
        text(
            """
            SELECT AVG(rr.finish_position)
            FROM race_results rr
            JOIN races r ON r.id = rr.race_id
            WHERE rr.constructor_id = :cid
              AND r.circuit_id = :circuit
              AND rr.finish_position IS NOT NULL
              AND r.date < :race_date
              AND r.is_completed = TRUE
            """
        ),
        {"cid": constructor_id, "circuit": circuit_id, "race_date": race_date},
    ).scalar()
    return float(val) if val is not None else None


def _is_wet_race_forecast(conn: Connection, race_id: int) -> bool:
    """Check the latest weather snapshot for rain probability >= 50%."""
    val = conn.execute(
        text(
            """
            SELECT rain_probability
            FROM weather_snapshots
            WHERE race_id = :rid
            ORDER BY captured_at DESC
            LIMIT 1
            """
        ),
        {"rid": race_id},
    ).scalar()
    if val is None:
        return False
    return float(val) >= 50.0


def _driver_wet_race_avg_position(conn: Connection, driver_id: int, race_date: object) -> float | None:
    val = conn.execute(
        text(
            """
            SELECT AVG(rr.finish_position)
            FROM race_results rr
            JOIN races r ON r.id = rr.race_id
            WHERE rr.driver_id = :did
              AND rr.is_wet_race = TRUE
              AND rr.finish_position IS NOT NULL
              AND r.date < :race_date
              AND r.is_completed = TRUE
            """
        ),
        {"did": driver_id, "race_date": race_date},
    ).scalar()
    return float(val) if val is not None else None


def _constructor_wet_race_avg_position(conn: Connection, constructor_id: int, race_date: object) -> float | None:
    val = conn.execute(
        text(
            """
            SELECT AVG(rr.finish_position)
            FROM race_results rr
            JOIN races r ON r.id = rr.race_id
            WHERE rr.constructor_id = :cid
              AND rr.is_wet_race = TRUE
              AND rr.finish_position IS NOT NULL
              AND r.date < :race_date
              AND r.is_completed = TRUE
            """
        ),
        {"cid": constructor_id, "race_date": race_date},
    ).scalar()
    return float(val) if val is not None else None


def _driver_season_avg_position(conn: Connection, driver_id: int, season: int, race_date: object) -> float | None:
    val = conn.execute(
        text(
            """
            SELECT AVG(rr.finish_position)
            FROM race_results rr
            JOIN races r ON r.id = rr.race_id
            WHERE rr.driver_id = :did
              AND r.season = :season
              AND rr.finish_position IS NOT NULL
              AND r.date < :race_date
              AND r.is_completed = TRUE
            """
        ),
        {"did": driver_id, "season": season, "race_date": race_date},
    ).scalar()
    return float(val) if val is not None else None


def _championship_position(conn: Connection, driver_id: int, season: int, race_date: object) -> int | None:
    """Driver's championship standing at the time of the race.

    Computed by summing points from all completed races in the season
    that occurred before the given race date, then ranking all drivers.
    """
    rows = conn.execute(
        text(
            """
            SELECT rr.driver_id, SUM(rr.points) AS total_points
            FROM race_results rr
            JOIN races r ON r.id = rr.race_id
            WHERE r.season = :season
              AND r.date < :race_date
              AND r.is_completed = TRUE
            GROUP BY rr.driver_id
            ORDER BY total_points DESC
            """
        ),
        {"season": season, "race_date": race_date},
    ).fetchall()
    if not rows:
        return None
    for position, row in enumerate(rows, start=1):
        if row[0] == driver_id:
            return position
    # Driver hasn't scored in any prior race this season
    return None


# ---------------------------------------------------------------------------
# Upsert feature row into the database
# ---------------------------------------------------------------------------


def _upsert_feature(conn: Connection, race_id: int, driver_id: int, feature_data: dict) -> None:
    conn.execute(
        text(
            """
            INSERT INTO features (race_id, driver_id, generated_at, feature_data)
            VALUES (:race_id, :driver_id, :generated_at, :feature_data)
            ON CONFLICT (race_id, driver_id) DO UPDATE
                SET generated_at = EXCLUDED.generated_at,
                    feature_data = EXCLUDED.feature_data
            """
        ),
        {
            "race_id": race_id,
            "driver_id": driver_id,
            "generated_at": datetime.now(timezone.utc),
            "feature_data": json.dumps(feature_data),
        },
    )


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def build_features_for_race(race_id: int, engine: Engine) -> pd.DataFrame:
    """Generate feature rows for every driver entered in the given race.

    Returns a DataFrame and also persists to the features table.
    """
    with engine.begin() as conn:
        race = _get_race_info(conn, race_id)
        drivers = _get_entered_drivers(conn, race_id)
        if not drivers:
            logger.warning("No drivers found for race %d", race_id)
            return pd.DataFrame()

        is_wet = _is_wet_race_forecast(conn, race_id)

        rows: list[dict] = []
        for entry in drivers:
            did = entry["driver_id"]
            cid = entry["constructor_id"]

            feature_data = {
                "grid_position": _grid_position(conn, race_id, did),
                "driver_avg_position_last_3_races": _driver_avg_position_last_n(conn, did, race["date"], n=3),
                "driver_avg_position_at_circuit": _driver_avg_position_at_circuit(
                    conn, did, race["circuit_id"], race["date"]
                ),
                "driver_podium_rate_at_circuit": _driver_podium_rate_at_circuit(
                    conn, did, race["circuit_id"], race["date"]
                ),
                "constructor_avg_position_last_3_races": _constructor_avg_position_last_n(conn, cid, race["date"], n=3),
                "constructor_avg_position_at_circuit": _constructor_avg_position_at_circuit(
                    conn, cid, race["circuit_id"], race["date"]
                ),
                "circuit_type": race["circuit_type"],
                "is_wet_race_forecast": is_wet,
                "driver_wet_race_avg_position": _driver_wet_race_avg_position(conn, did, race["date"]),
                "constructor_wet_race_avg_position": _constructor_wet_race_avg_position(conn, cid, race["date"]),
                "driver_season_avg_position": _driver_season_avg_position(conn, did, race["season"], race["date"]),
                "championship_position": _championship_position(conn, did, race["season"], race["date"]),
            }

            _upsert_feature(conn, race_id, did, feature_data)

            rows.append({"race_id": race_id, "driver_id": did, **feature_data})

        logger.info("Built features for %d drivers in race %d", len(rows), race_id)

    return pd.DataFrame(rows)


def export_parquet(df: pd.DataFrame, race_id: int) -> Path:
    """Write feature DataFrame to a Parquet file and return the path."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"features_{race_id}.parquet"
    df.to_parquet(path, index=False)
    logger.info("Exported features to %s", path)
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Build feature rows for a given race.")
    parser.add_argument("--race_id", type=int, required=True, help="ID of the race")
    args = parser.parse_args()

    engine = get_engine()
    df = build_features_for_race(args.race_id, engine)
    if df.empty:
        logger.warning("No features generated — exiting")
        return

    export_parquet(df, args.race_id)
    logger.info("Done — %d rows", len(df))


if __name__ == "__main__":
    main()
