"""One-shot bootstrap — ingest all historical data, train, predict, and evaluate.

Run this after starting the database to fully populate it for the 2026 season:

    docker-compose run --rm pipeline python -m pipeline.bootstrap

Steps:
  0. Enable FastF1 cache and sync the 2026 calendar first (avoids rate-limit
     failures after heavy historical fetching)
  1. Backfill historical seasons (2022, 2023, 2024, 2025) needed to train the model
  2. For each 2026 past round: ingest qualifying results and race results
  3. Build feature rows and export Parquet files for all completed races
  4. Train the pre-season XGBoost model on the exported Parquet files
  5. Replay each completed race to retrain/evaluate/predict as if the scheduler
     had been running since pre-season
"""

import logging
import sys
from datetime import date
from pathlib import Path

import fastf1

from pipeline.features.builder import build_features_for_race, export_parquet
from pipeline.ingest.calendar_sync import sync_season_calendar
from pipeline.ingest.fetch_qualifying import ingest_event as ingest_qualifying
from pipeline.ingest.fetch_results import ingest_event as ingest_results
from pipeline.ingest.upsert_helpers import get_engine
from pipeline.maintenance.driver_metadata import backfill_driver_numbers
from pipeline.ml.predict import run as predict
from pipeline.ml.train import run as train
from pipeline.ml.workflow import post_race_pipeline, predict_remaining_races

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
for noisy in ("fastf1", "req", "core", "logger", "_api"):
    logging.getLogger(noisy).setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)

SEASON = 2026
HISTORICAL_SEASONS = [2022, 2023, 2024, 2025]
ARTIFACTS_DIR = Path(__file__).resolve().parent / "ml" / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "model_v1.json"
DATA_DIR = Path(__file__).resolve().parent / "data"


def main() -> None:
    engine = get_engine()

    # Enable FastF1 cache so session data is persisted across container runs
    # and we avoid hammering the F1 API for data we already have.
    cache_dir = DATA_DIR / "fastf1_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    logger.info("FastF1 cache enabled at %s", cache_dir)

    backfill_driver_numbers(engine)

    # ------------------------------------------------------------------
    # Step 1 — Sync 2026 calendar FIRST (before heavy historical fetching
    # to avoid hitting the API rate limit before we have the 2026 data)
    # ------------------------------------------------------------------
    logger.info("=== Step 1: Syncing %d calendar ===", SEASON)
    events = sync_season_calendar(SEASON, engine)
    if not events:
        logger.error("No events returned — FastF1 calendar may not be available yet")
        sys.exit(1)
    logger.info("Calendar synced — %d events", len(events))

    today = date.today()
    completed_events = sorted((e for e in events if e["event_date"] < today), key=lambda e: e["round"])
    upcoming_events = sorted((e for e in events if e["event_date"] >= today), key=lambda e: e["round"])
    next_event = upcoming_events[0] if upcoming_events else None

    logger.info(
        "Completed: %d races | Upcoming: %d | Next: %s",
        len(completed_events),
        len(upcoming_events),
        next_event["name"] if next_event else "none",
    )

    # ------------------------------------------------------------------
    # Step 0 — Backfill historical seasons for model training
    # ------------------------------------------------------------------
    logger.info("=== Step 0: Backfilling historical seasons %s ===", HISTORICAL_SEASONS)
    for hist_season in HISTORICAL_SEASONS:
        logger.info("  Syncing %d calendar…", hist_season)
        hist_events = sync_season_calendar(hist_season, engine)
        hist_completed = sorted((e for e in hist_events if e["event_date"] < today), key=lambda e: e["round"])
        logger.info("  %d: %d completed races to ingest", hist_season, len(hist_completed))
        for event in hist_completed:
            round_num = event["round"]
            race_id = event["race_id"]
            logger.info("    %d R%02d — %s", hist_season, round_num, event["name"])
            try:
                ingest_qualifying(hist_season, round_num, engine)
            except Exception as exc:
                logger.warning("      Qualifying ingest failed: %s", exc)
            try:
                ingest_results(hist_season, round_num, engine)
            except Exception as exc:
                logger.warning("      Results ingest failed: %s", exc)
            try:
                df = build_features_for_race(race_id, engine)
                if not df.empty:
                    export_parquet(df, race_id)
            except Exception as exc:
                logger.warning("      Feature build failed: %s", exc)

    # ------------------------------------------------------------------
    # Step 2 — Ingest qualifying + results for completed races
    # ------------------------------------------------------------------
    logger.info("=== Step 2: Ingesting historical data ===")
    for event in completed_events:
        round_num = event["round"]
        logger.info("  Round %02d — %s: qualifying…", round_num, event["name"])
        try:
            ingest_qualifying(SEASON, round_num, engine)
        except Exception as exc:
            logger.warning("    Qualifying ingest failed: %s", exc)

        logger.info("  Round %02d — %s: results…", round_num, event["name"])
        try:
            ingest_results(SEASON, round_num, engine)
        except Exception as exc:
            logger.warning("    Results ingest failed: %s", exc)

    # Also ingest qualifying for the next upcoming race (needed for grid positions)
    if next_event:
        logger.info("  Round %02d — %s: qualifying (next race)…", next_event["round"], next_event["name"])
        try:
            ingest_qualifying(SEASON, next_event["round"], engine)
        except Exception as exc:
            logger.warning("    Qualifying ingest failed: %s", exc)

    # ------------------------------------------------------------------
    # Step 3 — Build features and export Parquet files
    # ------------------------------------------------------------------
    logger.info("=== Step 3: Building features ===")
    # Include all upcoming races so predict_remaining_races can generate pre-weekend
    # predictions for events that do not yet have qualifying data.  The feature
    # builder falls back to driver_contracts when no qualifying data is present.
    races_for_features = completed_events + upcoming_events
    parquet_count = 0
    for event in races_for_features:
        race_id = event["race_id"]
        logger.info("  Race %d — %s", race_id, event["name"])
        try:
            df = build_features_for_race(race_id, engine)
            if df.empty:
                logger.warning("    No features generated — skipping")
                continue
            export_parquet(df, race_id)
            parquet_count += 1
        except Exception as exc:
            logger.warning("    Feature build failed: %s", exc)

    if parquet_count == 0:
        logger.error("No Parquet files generated — cannot train model")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 4 — Train baseline model
    # ------------------------------------------------------------------
    logger.info("=== Step 4: Training baseline model ===")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        current_model_version_id = train(data_dir=DATA_DIR, artifact_path=MODEL_PATH, engine=engine)
        logger.info("Baseline model trained — model_version_id=%d", current_model_version_id)
    except Exception as exc:
        logger.error("Training failed: %s", exc)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 5 — Replay completed races to mimic scheduler retrains
    # ------------------------------------------------------------------
    completed_events_sorted = sorted(completed_events, key=lambda e: e["round"])
    if not completed_events_sorted:
        logger.info("No completed races to replay — seeding predictions for upcoming events.")
        predict_remaining_races(SEASON, current_model_version_id, engine)
    else:
        logger.info("=== Step 5: Replaying %d completed races ===", len(completed_events_sorted))
        for event in completed_events_sorted:
            race_id = event["race_id"]
            logger.info("  Round %02d — %s: regenerating pre-race predictions", event["round"], event["name"])
            try:
                predict(
                    race_id=race_id,
                    model_version_id=current_model_version_id,
                    model_path=MODEL_PATH,
                    engine=engine,
                )
            except Exception as exc:
                logger.warning("    Prediction failed: %s", exc)

            new_model_id = post_race_pipeline(race_id, SEASON, engine)
            if new_model_id:
                current_model_version_id = new_model_id

    logger.info("=== Bootstrap complete ===")
    logger.info(
        "Replayed %d completed races; latest model_version_id=%d.",
        len(completed_events_sorted),
        current_model_version_id,
    )


if __name__ == "__main__":
    main()
