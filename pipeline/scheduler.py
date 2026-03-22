"""APScheduler entry point — calendar-aware ingestion scheduler."""

import argparse
import logging
import signal
import sys
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.ingest.calendar_sync import sync_season_calendar
from pipeline.ingest.fetch_qualifying import ingest_event as ingest_qualifying_event
from pipeline.ingest.fetch_results import ingest_event as ingest_results_event
from pipeline.ingest.fetch_weather import fetch_and_store_weather
from pipeline.ingest.upsert_helpers import get_engine
from pipeline.ml import workflow as ml_workflow

post_race_pipeline = ml_workflow.post_race_pipeline
_get_latest_model_version_id_for_race = ml_workflow._get_latest_model_version_id_for_race
_get_remaining_race_ids = ml_workflow._get_remaining_race_ids

# Back-compat aliases for unit tests that patch scheduler-level names.
build_features_for_race = ml_workflow.build_features_for_race
export_parquet = ml_workflow.export_parquet
ml_train = ml_workflow.ml_train
ml_evaluate = ml_workflow.ml_evaluate
ml_predict = ml_workflow.ml_predict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
for _noisy in ("fastf1", "req", "core", "logger", "_api", "apscheduler"):
    logging.getLogger(_noisy).setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable grace periods
# ---------------------------------------------------------------------------

QUALIFYING_GRACE_MINUTES = 45
RACE_GRACE_MINUTES = 60
WEATHER_INITIAL_DAYS_BEFORE = 5
WEATHER_REFRESH_AFTER_QUALI_MINUTES = 30

# ---------------------------------------------------------------------------
# Job type identifiers
# ---------------------------------------------------------------------------

JOB_WEATHER_INITIAL = "weather_initial"
JOB_WEATHER_REFRESH = "weather_refresh"
JOB_QUALIFYING = "qualifying_results"
JOB_RACE = "race_results"

ALL_JOB_TYPES = [JOB_WEATHER_INITIAL, JOB_WEATHER_REFRESH, JOB_QUALIFYING, JOB_RACE]


# ---------------------------------------------------------------------------
# Job timing computation
# ---------------------------------------------------------------------------


def _find_session_time(session_times: dict[str, datetime], target: str) -> datetime | None:
    """Find a session time by name, case-insensitive."""
    for name, dt in session_times.items():
        if name.lower() == target.lower():
            return dt
    return None


def _compute_job_times(event: dict) -> list[tuple[str, datetime]]:
    """Compute (job_type, run_at_utc) pairs for an event."""
    session_times = event["session_times"]
    quali_time = _find_session_time(session_times, "Qualifying")
    race_time = _find_session_time(session_times, "Race")

    jobs: list[tuple[str, datetime]] = []

    if race_time:
        jobs.append(
            (
                JOB_WEATHER_INITIAL,
                race_time - timedelta(days=WEATHER_INITIAL_DAYS_BEFORE),
            )
        )
        jobs.append(
            (
                JOB_RACE,
                race_time + timedelta(minutes=RACE_GRACE_MINUTES),
            )
        )

    if quali_time:
        jobs.append(
            (
                JOB_WEATHER_REFRESH,
                quali_time + timedelta(minutes=WEATHER_REFRESH_AFTER_QUALI_MINUTES),
            )
        )
        jobs.append(
            (
                JOB_QUALIFYING,
                quali_time + timedelta(minutes=QUALIFYING_GRACE_MINUTES),
            )
        )

    return jobs


# ---------------------------------------------------------------------------
# Job ID helpers
# ---------------------------------------------------------------------------


def _make_job_id(job_type: str, season: int, round_num: int) -> str:
    return f"{job_type}_{season}_R{round_num:02d}"


# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------


def _run_job(job_type: str, season: int, round_num: int, race_id: int, engine: Engine) -> None:
    logger.info(
        "Job [%s] starting — season %d round %d (race_id=%d)",
        job_type,
        season,
        round_num,
        race_id,
    )
    try:
        if job_type in (JOB_WEATHER_INITIAL, JOB_WEATHER_REFRESH):
            fetch_and_store_weather(race_id, engine)
        elif job_type == JOB_QUALIFYING:
            ingest_qualifying_event(season, round_num, engine)
        elif job_type == JOB_RACE:
            ingested = ingest_results_event(season, round_num, engine)
            if ingested:
                post_race_pipeline(race_id, season, engine)
            else:
                logger.info(
                    "_run_job: ingest returned no data for race_id=%d — skipping post_race_pipeline",
                    race_id,
                )
        else:
            logger.error("Unknown job type: %s", job_type)
            return
        logger.info("Job [%s] completed — season %d round %d", job_type, season, round_num)
    except Exception:
        logger.exception("Job [%s] failed — season %d round %d", job_type, season, round_num)


# ---------------------------------------------------------------------------
# Catch-up logic
# ---------------------------------------------------------------------------


def _should_catch_up(job_type: str, event: dict, engine: Engine) -> bool:
    """Determine whether a missed job should be caught up."""
    race_id = event["race_id"]
    session_times = event["session_times"]
    now = datetime.now(timezone.utc)

    with engine.begin() as conn:
        if job_type == JOB_QUALIFYING:
            count = conn.execute(
                text("SELECT COUNT(*) FROM qualifying_results WHERE race_id = :rid"),
                {"rid": race_id},
            ).scalar()
            return count == 0

        if job_type == JOB_RACE:
            row = conn.execute(
                text("""
                    SELECT is_completed,
                           (SELECT COUNT(*) FROM race_results WHERE race_id = :rid),
                           (SELECT COUNT(*) FROM predictions WHERE race_id = :rid)
                    FROM races WHERE id = :rid
                """),
                {"rid": race_id},
            ).fetchone()
            if row is None:
                return False
            is_completed, result_count, prediction_count = row
            # Skip if race already completed, results already present, or predictions
            # already generated (post_race_pipeline already ran, e.g. via bootstrap).
            if is_completed or result_count > 0 or prediction_count > 0:
                return False
            return True

        if job_type == JOB_WEATHER_INITIAL:
            race_time = _find_session_time(session_times, "Race")
            if race_time and race_time > now:
                is_completed = conn.execute(
                    text("SELECT is_completed FROM races WHERE id = :rid"),
                    {"rid": race_id},
                ).scalar()
                if is_completed is None:
                    return False
                return not is_completed
            return False

        if job_type == JOB_WEATHER_REFRESH:
            quali_time = _find_session_time(session_times, "Qualifying")
            race_time = _find_session_time(session_times, "Race")
            if quali_time and race_time and quali_time < now < race_time:
                is_completed = conn.execute(
                    text("SELECT is_completed FROM races WHERE id = :rid"),
                    {"rid": race_id},
                ).scalar()
                if is_completed is None:
                    return False
                return not is_completed
            return False

    return False


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def _schedule_events(
    scheduler: BlockingScheduler,
    events: list[dict],
    engine: Engine,
) -> None:
    """Register one-off jobs for each event based on actual session times."""
    now = datetime.now(timezone.utc)

    for event in events:
        job_times = _compute_job_times(event)
        for job_type, run_at in job_times:
            job_id = _make_job_id(job_type, event["season"], event["round"])

            if run_at > now:
                scheduler.add_job(
                    _run_job,
                    trigger=DateTrigger(run_date=run_at),
                    args=[job_type, event["season"], event["round"], event["race_id"], engine],
                    id=job_id,
                    replace_existing=True,
                )
                logger.info("Scheduled %-45s at %s", job_id, run_at.isoformat())
            else:
                if _should_catch_up(job_type, event, engine):
                    logger.info("Catch-up: %s — data absent, running now", job_id)
                    _run_job(job_type, event["season"], event["round"], event["race_id"], engine)
                else:
                    logger.debug("Skipped %s — already done or not applicable", job_id)


def _list_jobs(scheduler: BlockingScheduler) -> None:
    """Log all registered jobs and their next run times."""
    jobs = scheduler.get_jobs()
    if not jobs:
        logger.info("No future jobs scheduled.")
        return
    logger.info("Scheduled jobs (%d):", len(jobs))
    _min = datetime.min.replace(tzinfo=timezone.utc)
    for job in sorted(jobs, key=lambda j: getattr(j, "next_run_time", None) or _min):
        next_run_time = getattr(job, "next_run_time", None)
        next_run = next_run_time.isoformat() if next_run_time else "N/A"
        logger.info("  %-45s  next run: %s", job.id, next_run)


# ---------------------------------------------------------------------------
# Manual trigger
# ---------------------------------------------------------------------------


def _manual_trigger(job_type: str, season: int, round_num: int, engine: Engine) -> None:
    """Run a single job immediately for a given event."""
    events = sync_season_calendar(season, engine)
    event = next((e for e in events if e["round"] == round_num), None)
    if event is None:
        logger.error("Round %d not found in season %d calendar", round_num, season)
        sys.exit(1)
    logger.info("Manual trigger: %s for %s (round %d)", job_type, event["name"], round_num)
    _run_job(job_type, season, round_num, event["race_id"], engine)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    active_season = datetime.now(timezone.utc).year

    parser = argparse.ArgumentParser(description="GridOracle pipeline scheduler")
    parser.add_argument(
        "--trigger",
        choices=ALL_JOB_TYPES,
        default=None,
        help="Manually trigger a specific job type",
    )
    parser.add_argument("--season", type=int, default=active_season)
    parser.add_argument("--round", type=int, default=None, help="Round number (required for --trigger)")
    args = parser.parse_args()

    engine = get_engine()

    if args.trigger:
        if args.round is None:
            parser.error("--round is required for manual triggers")
        _manual_trigger(args.trigger, args.season, args.round, engine)
        return

    # Normal scheduler startup
    logger.info("Pipeline scheduler starting for season %d", args.season)

    events = sync_season_calendar(args.season, engine)
    if not events:
        logger.warning("No events found for season %d — calendar may not be available yet", args.season)

    scheduler = BlockingScheduler(timezone=timezone.utc)
    _schedule_events(scheduler, events, engine)
    _list_jobs(scheduler)

    def _shutdown(signum, frame):
        logger.info("Shutting down scheduler…")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("Scheduler running. Waiting for jobs…")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
