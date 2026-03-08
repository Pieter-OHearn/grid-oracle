"""Shared database upsert helpers for the ingest pipeline."""

import logging
import os

import fastf1
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Placeholder hex colour when a constructor has no known colour.
UNKNOWN_COLOR = "#000000"


def get_engine() -> Engine:
    db_url = os.environ["DATABASE_URL"]
    return create_engine(db_url)


def upsert_circuit(conn, session: fastf1.core.Session) -> int:
    """Insert circuit if absent; return its id."""
    name = session.event["EventName"]
    country = session.event["Country"]
    city = session.event["Location"]
    # FastF1 doesn't expose circuit_type / total_laps / length_km directly;
    # use sensible defaults so the row can be enriched later.
    row = conn.execute(
        text(
            """
            INSERT INTO circuits (name, country, city, circuit_type, total_laps, length_km)
            VALUES (:name, :country, :city, 'unknown', 0, 0)
            ON CONFLICT (name) DO UPDATE
                SET country = EXCLUDED.country,
                    city    = EXCLUDED.city
            RETURNING id
            """
        ),
        {"name": name, "country": country, "city": city},
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(text("SELECT id FROM circuits WHERE name = :name"), {"name": name}).scalar_one()


def upsert_race(
    conn,
    season: int,
    round_num: int,
    name: str,
    circuit_id: int,
    date,
    *,
    mark_completed: bool = False,
) -> int:
    """Insert or update a race row.

    When mark_completed=True (race results path), is_completed is set to TRUE
    and held at TRUE on conflict. When False (qualifying path), is_completed is
    not touched on conflict so an existing TRUE value is never downgraded.
    """
    if mark_completed:
        sql = """
            INSERT INTO races (season, round, name, circuit_id, date, is_completed)
            VALUES (:season, :round, :name, :circuit_id, :date, TRUE)
            ON CONFLICT (season, round) DO UPDATE
                SET name         = EXCLUDED.name,
                    circuit_id   = EXCLUDED.circuit_id,
                    date         = EXCLUDED.date,
                    is_completed = TRUE
            RETURNING id
        """
    else:
        sql = """
            INSERT INTO races (season, round, name, circuit_id, date, is_completed)
            VALUES (:season, :round, :name, :circuit_id, :date, FALSE)
            ON CONFLICT (season, round) DO UPDATE
                SET name       = EXCLUDED.name,
                    circuit_id = EXCLUDED.circuit_id,
                    date       = EXCLUDED.date
            RETURNING id
        """
    row = conn.execute(
        text(sql),
        {"season": season, "round": round_num, "name": name, "circuit_id": circuit_id, "date": date},
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(
        text("SELECT id FROM races WHERE season = :s AND round = :r"),
        {"s": season, "r": round_num},
    ).scalar_one()


def upsert_driver(conn, code: str, full_name: str, nationality: str) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO drivers (code, full_name, nationality)
            VALUES (:code, :full_name, :nationality)
            ON CONFLICT (code) DO UPDATE
                SET full_name   = EXCLUDED.full_name,
                    nationality = EXCLUDED.nationality
            RETURNING id
            """
        ),
        {"code": code, "full_name": full_name, "nationality": nationality},
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(text("SELECT id FROM drivers WHERE code = :code"), {"code": code}).scalar_one()


def upsert_constructor(conn, name: str, nationality: str) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO constructors (name, nationality, color_hex)
            VALUES (:name, :nationality, :color)
            ON CONFLICT (name) DO UPDATE
                SET nationality = EXCLUDED.nationality
            RETURNING id
            """
        ),
        {"name": name, "nationality": nationality, "color": UNKNOWN_COLOR},
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(text("SELECT id FROM constructors WHERE name = :name"), {"name": name}).scalar_one()


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
