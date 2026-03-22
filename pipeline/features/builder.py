"""Feature engineering module — generates one feature row per driver per race."""

import argparse
import json
import logging
import statistics
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
    """Return drivers entered in the race.

    Uses qualifying/race results when available (race weekend has started).
    Falls back to driver_contracts for pre-weekend predictions where no session
    data has been ingested yet.
    """
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT d.id AS driver_id, dc.constructor_id
            FROM (
                SELECT driver_id FROM qualifying_results WHERE race_id = :rid
                UNION
                SELECT driver_id FROM race_results WHERE race_id = :rid
            ) sub
            JOIN drivers d ON d.id = sub.driver_id
            JOIN races r ON r.id = :rid
            JOIN driver_contracts dc
              ON dc.driver_id = d.id
             AND dc.season = r.season
             AND dc.start_round <= r.round
             AND (dc.end_round IS NULL OR dc.end_round >= r.round)
            """
        ),
        {"rid": race_id},
    ).fetchall()

    if rows:
        return [{"driver_id": r[0], "constructor_id": r[1]} for r in rows]

    # Pre-weekend fallback: no qualifying or race data yet — use driver_contracts
    logger.info("No session data for race %d — using driver_contracts for driver lineup", race_id)
    rows = conn.execute(
        text(
            """
            SELECT dc.driver_id, dc.constructor_id
            FROM driver_contracts dc
            JOIN races r ON r.id = :rid
            WHERE dc.season = r.season
              AND dc.start_round <= r.round
              AND (dc.end_round IS NULL OR dc.end_round >= r.round)
            ORDER BY dc.driver_id
            """
        ),
        {"rid": race_id},
    ).fetchall()
    return [{"driver_id": r[0], "constructor_id": r[1]} for r in rows]


def _grid_position(conn: Connection, race_id: int, driver_id: int) -> int | None:
    """Actual starting grid position (post-penalty) from qualifying results."""
    return conn.execute(
        text(
            """
            SELECT grid_position + COALESCE(grid_penalty, 0)
            FROM qualifying_results
            WHERE race_id = :rid AND driver_id = :did
            """
        ),
        {"rid": race_id, "did": driver_id},
    ).scalar()


def _driver_avg_qualifying_position_at_circuit(
    conn: Connection, driver_id: int, circuit_id: int, race_date: object
) -> float | None:
    """Historical average actual starting position at a circuit before race_date."""
    val = conn.execute(
        text(
            """
            SELECT AVG(qr.grid_position + COALESCE(qr.grid_penalty, 0))
            FROM qualifying_results qr
            JOIN races r ON r.id = qr.race_id
            WHERE qr.driver_id = :did
              AND r.circuit_id = :cid
              AND qr.grid_position IS NOT NULL
              AND r.date < :race_date
              AND r.is_completed = TRUE
            """
        ),
        {"did": driver_id, "cid": circuit_id, "race_date": race_date},
    ).scalar()
    return float(val) if val is not None else None


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


def _constructor_dnf_rate_last_season(conn: Connection, constructor_id: int, season: int) -> float | None:
    """Proportion of races where the constructor had at least one DNF in the previous season.

    ``season`` is the current race season; the function queries ``season - 1``
    internally. A DNF is any result where status != 'Finished' and not a lapped
    finish. FastF1 encodes lapped finishers as '+1 Lap', '+2 Laps', etc., so we
    exclude those with NOT LIKE '+% Lap%'.
    Returns None if the constructor has no results in the previous season.
    """
    row = conn.execute(
        text(
            """
            SELECT
                COUNT(DISTINCT rr.race_id) FILTER (
                    WHERE rr.status != 'Finished' AND rr.status NOT LIKE '+%% Lap%%'
                ) AS dnf_races,
                COUNT(DISTINCT rr.race_id) AS total_races
            FROM race_results rr
            JOIN races r ON r.id = rr.race_id
            WHERE rr.constructor_id = :cid
              AND r.season = :prev_season
              AND r.is_completed = TRUE
            """
        ),
        {"cid": constructor_id, "prev_season": season - 1},
    ).fetchone()
    if row is None or row[1] == 0:
        return None
    return float(row[0]) / float(row[1])


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


def _driver_standings(conn: Connection, season: int, race_date: object) -> dict[int, int]:
    """Return {driver_id: championship_position} for all point-scorers before race_date.

    Position is 1-based, ordered by total points descending.  Returns an empty
    dict when no races have been completed yet (round 1 of a season) — callers
    treat an empty dict as all drivers tied at position 1.
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
    return {row[0]: pos for pos, row in enumerate(rows, start=1)}


def _constructor_standings(conn: Connection, season: int, race_date: object) -> dict[int, int]:
    """Return {constructor_id: championship_position} for all point-scorers before race_date.

    Position is 1-based, ordered by total constructor points descending.  Returns
    an empty dict when no races have been completed yet (round 1).
    """
    rows = conn.execute(
        text(
            """
            SELECT rr.constructor_id, SUM(rr.points) AS total_points
            FROM race_results rr
            JOIN races r ON r.id = rr.race_id
            WHERE r.season = :season
              AND r.date < :race_date
              AND r.is_completed = TRUE
            GROUP BY rr.constructor_id
            ORDER BY total_points DESC
            """
        ),
        {"season": season, "race_date": race_date},
    ).fetchall()
    return {row[0]: pos for pos, row in enumerate(rows, start=1)}


def _driver_avg_sector2_time_at_circuit(
    conn: Connection, driver_id: int, circuit_id: int, race_date: object
) -> float | None:
    """Historical average of driver's sector-2 time relative to session fastest at circuit.

    For each prior qualifying session at this circuit, compute the ratio of
    the driver's best sector-2 time to the fastest sector-2 time in that session,
    then return the average ratio across sessions.  A value of 1.0 means the
    driver was the fastest; higher values mean they were slower.
    Returns None when no qualifying sector data is available.
    """
    val = conn.execute(
        text(
            """
            SELECT AVG(sub.ratio)
            FROM (
                SELECT st.sector2_ms::float / fastest.min_s2::float AS ratio
                FROM session_times st
                JOIN races r ON r.id = st.race_id
                JOIN (
                    SELECT race_id, MIN(sector2_ms) AS min_s2
                    FROM session_times
                    WHERE session_type = 'Q' AND sector2_ms IS NOT NULL
                    GROUP BY race_id
                ) fastest ON fastest.race_id = st.race_id
                WHERE st.driver_id = :did
                  AND r.circuit_id = :cid
                  AND st.session_type = 'Q'
                  AND st.sector2_ms IS NOT NULL
                  AND r.date < :race_date
                  AND r.is_completed = TRUE
            ) sub
            """
        ),
        {"did": driver_id, "cid": circuit_id, "race_date": race_date},
    ).scalar()
    return float(val) if val is not None else None


def _constructor_avg_fp2_pace_at_circuit(
    conn: Connection, constructor_id: int, circuit_id: int, race_date: object
) -> float | None:
    """Historical average of constructor's FP2 pace relative to session fastest at circuit.

    For each prior FP2 session at this circuit, compute the ratio of the
    constructor's best lap time (minimum across its two drivers) to the
    fastest FP2 lap in that session, then return the average ratio.
    Returns None when no FP2 data is available.
    """
    val = conn.execute(
        text(
            """
            SELECT AVG(sub.ratio)
            FROM (
                SELECT MIN(st.best_lap_ms)::float / fastest.min_lap::float AS ratio
                FROM session_times st
                JOIN races r ON r.id = st.race_id
                JOIN driver_contracts dc
                  ON dc.driver_id    = st.driver_id
                 AND dc.constructor_id = :cid
                 AND dc.season         = r.season
                 AND dc.start_round   <= r.round
                 AND (dc.end_round IS NULL OR dc.end_round >= r.round)
                JOIN (
                    SELECT race_id, MIN(best_lap_ms) AS min_lap
                    FROM session_times
                    WHERE session_type = 'FP2' AND best_lap_ms IS NOT NULL
                    GROUP BY race_id
                ) fastest ON fastest.race_id = st.race_id
                WHERE r.circuit_id = :circuit
                  AND st.session_type = 'FP2'
                  AND st.best_lap_ms IS NOT NULL
                  AND r.date < :race_date
                  AND r.is_completed = TRUE
                GROUP BY r.id, fastest.min_lap
            ) sub
            """
        ),
        {"cid": constructor_id, "circuit": circuit_id, "race_date": race_date},
    ).scalar()
    return float(val) if val is not None else None


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

        has_qualifying = (
            conn.execute(
                text("SELECT COUNT(*) FROM qualifying_results WHERE race_id = :rid"),
                {"rid": race_id},
            ).scalar()
            > 0
        )

        # Fetch championship standings once per race (not once per driver).
        # An empty dict means round 1 — everyone defaults to position 1.
        driver_champ = _driver_standings(conn, race["season"], race["date"])
        constructor_champ = _constructor_standings(conn, race["season"], race["date"])
        driver_champ_default = 1 if not driver_champ else len(driver_champ) + 1
        constructor_champ_default = 1 if not constructor_champ else len(constructor_champ) + 1

        rows: list[dict] = []
        for entry in drivers:
            did = entry["driver_id"]
            cid = entry["constructor_id"]

            if has_qualifying:
                grid_pos = _grid_position(conn, race_id, did)
            else:
                grid_pos = _driver_avg_qualifying_position_at_circuit(conn, did, race["circuit_id"], race["date"])

            feature_data = {
                "grid_position": grid_pos,
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
                "driver_championship_position": driver_champ.get(did, driver_champ_default),
                "constructor_championship_position": constructor_champ.get(cid, constructor_champ_default),
                "constructor_dnf_rate_last_season": _constructor_dnf_rate_last_season(conn, cid, race["season"]),
                # Sector / practice pace features — normalised ratios relative to session fastest.
                # None here; imputed with circuit median below after all drivers are processed.
                "driver_avg_sector2_time_at_circuit": _driver_avg_sector2_time_at_circuit(
                    conn, did, race["circuit_id"], race["date"]
                ),
                "constructor_avg_fp2_pace_at_circuit": _constructor_avg_fp2_pace_at_circuit(
                    conn, cid, race["circuit_id"], race["date"]
                ),
            }

            rows.append({"race_id": race_id, "driver_id": did, **feature_data})

        # Impute missing sector/FP2 features with the circuit median for this race.
        # If no driver has data (new circuit), default to 1.0 (no relative advantage).
        for col in ("driver_avg_sector2_time_at_circuit", "constructor_avg_fp2_pace_at_circuit"):
            non_null = [r[col] for r in rows if r[col] is not None]
            fill = statistics.median(non_null) if non_null else 1.0
            for r in rows:
                if r[col] is None:
                    r[col] = fill

        skip = {"race_id", "driver_id"}
        for r in rows:
            _upsert_feature(conn, race_id, r["driver_id"], {k: v for k, v in r.items() if k not in skip})

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
