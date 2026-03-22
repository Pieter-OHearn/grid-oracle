"""Backfill grid_penalty for existing qualifying_results rows.

Re-ingests qualifying data for the given seasons using the standard upsert,
which now writes grid_penalty derived from FastF1's GridPosition vs Position.
Safe to run multiple times — rows with no penalty will have grid_penalty set
to NULL, and rows that already have a correct value are unchanged by the upsert.

Usage (from inside the pipeline container or a local venv):

    python -m pipeline.maintenance.backfill_grid_penalties --seasons 2022 2023 2024 2025
"""

import argparse
import logging

from sqlalchemy import text

from pipeline.ingest.fetch_qualifying import ingest_season
from pipeline.ingest.upsert_helpers import get_engine

logger = logging.getLogger(__name__)


def backfill_grid_penalties(engine, seasons: list[int]) -> None:
    """Re-ingest qualifying data for each season to populate grid_penalty.

    For rows where GridPosition == Position (no penalty), grid_penalty is set
    to NULL. For rows where they differ (penalty drop or promotion), the delta
    is stored. Existing rows are updated via ON CONFLICT DO UPDATE.
    """
    with engine.connect() as conn:
        null_count = conn.execute(
            text("SELECT COUNT(*) FROM qualifying_results WHERE grid_penalty IS NULL")
        ).scalar()

    logger.info("Rows with NULL grid_penalty before backfill: %d", null_count)

    for season in seasons:
        logger.info("Backfilling grid penalties for season %d…", season)
        try:
            ingest_season(season, engine)
        except Exception as exc:
            logger.warning("Season %d backfill failed — %s", season, exc)

    with engine.connect() as conn:
        populated = conn.execute(
            text("SELECT COUNT(*) FROM qualifying_results WHERE grid_penalty IS NOT NULL")
        ).scalar()

    logger.info("Backfill complete — %d rows now have a non-NULL grid_penalty", populated)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Backfill grid_penalty for historical qualifying results.")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=[2022, 2023, 2024, 2025],
        help="Seasons to re-ingest (default: 2022 2023 2024 2025)",
    )
    args = parser.parse_args()

    engine = get_engine()
    backfill_grid_penalties(engine, args.seasons)


if __name__ == "__main__":
    main()
