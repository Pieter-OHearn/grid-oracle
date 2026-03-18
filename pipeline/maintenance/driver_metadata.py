"""Utilities for keeping driver metadata consistent in the database."""

from __future__ import annotations

import logging
from collections import defaultdict

import fastf1
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def backfill_driver_numbers(engine: Engine) -> None:
    """Populate drivers.number for any drivers missing a race number.

    Fetches FastF1 race results for each season present in the database
    until every driver has a known number. Safe to run multiple times.
    """
    with engine.connect() as conn:
        missing = conn.execute(text("SELECT code FROM drivers WHERE number IS NULL")).fetchall()
        if not missing:
            logger.info("Driver number backfill: no missing numbers detected")
            return
        seasons = [
            row[0]
            for row in conn.execute(text("SELECT DISTINCT season FROM races ORDER BY season")).fetchall()
        ]

    missing_codes = {row[0] for row in missing}
    logger.info("Driver number backfill: %d drivers missing numbers", len(missing_codes))

    for season in seasons:
        if not missing_codes:
            break
        try:
            schedule = fastf1.get_event_schedule(season, include_testing=False)
        except Exception as exc:
            logger.warning("Driver number backfill: failed to load schedule for %d — %s", season, exc)
            continue

        for _, event in schedule.iterrows():
            if not missing_codes:
                break
            round_num = int(event["RoundNumber"])
            try:
                session = fastf1.get_session(season, round_num, "R")
                session.load(laps=False, telemetry=False, weather=False, messages=False)
            except Exception as exc:
                logger.debug(
                    "Driver number backfill: failed to load season %d round %d — %s",
                    season,
                    round_num,
                    exc,
                )
                continue

            results = session.results
            if results is None or results.empty:
                continue

            updates: dict[str, int] = {}
            for _, row in results.iterrows():
                code = str(row.get("Abbreviation", ""))[:3]
                if code not in missing_codes:
                    continue
                number = row.get("DriverNumber")
                if number is None:
                    continue
                try:
                    updates[code] = int(number)
                except (TypeError, ValueError):
                    continue

            if not updates:
                continue

            with engine.begin() as conn:
                for code, number in updates.items():
                    conn.execute(
                        text("UPDATE drivers SET number = :number WHERE code = :code"),
                        {"number": number, "code": code},
                    )
                    missing_codes.discard(code)
                    logger.info(
                        "Driver number backfill: %s assigned #%d via season %d round %d",
                        code,
                        number,
                        season,
                        round_num,
                    )

    if missing_codes:
        logger.warning(
            "Driver number backfill: unable to determine numbers for %s",
            ", ".join(sorted(missing_codes)),
        )
    else:
        logger.info("Driver number backfill complete — all drivers now have numbers.")
