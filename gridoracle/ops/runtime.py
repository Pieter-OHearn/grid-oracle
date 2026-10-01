"""Separate HTTP, reconciliation, and bounded execution entry points."""

import argparse
import json
import os
import signal
import time
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, text

from gridoracle.ops.bundle import file_digest, verify_bundle


def configure() -> None:
    for name in ("DATABASE_URL",):
        if path := os.getenv(name + "_FILE"):
            os.environ[name] = Path(path).read_text().strip()
    if not os.getenv("DATABASE_URL"):
        raise ValueError("DATABASE_URL or DATABASE_URL_FILE is required")


def bundle_check() -> dict:
    return verify_bundle(
        Path(os.environ["GRIDORACLE_ARTIFACT_ROOT"]),
        Path(os.environ["GRIDORACLE_BUNDLE_FILE"]),
        os.environ["GRIDORACLE_BUNDLE_SHA256"],
    )


def scheduler_tick(engine, season: int) -> None:
    from pipeline.ingest.calendar_sync import (
        sync_season_calendar,
        to_orchestration_event,
    )
    from pipeline.orchestration import JobLedger
    from pipeline.scheduler import _active_entries

    ledger = JobLedger(engine)
    ledger.recover_expired_leases()
    for event in sync_season_calendar(season, engine):
        ledger.reconcile(
            to_orchestration_event(event, _active_entries(engine, event["race_id"]))
        )


def worker_tick(engine) -> bool:
    from pipeline.orchestration import EVALUATE, JobBlocked, JobLedger

    # The existing handler deliberately blocks unavailable provenance-aware
    # prediction/publication. Never enable the legacy automatic training path.
    ledger = JobLedger(engine)
    ledger.recover_expired_leases()
    job = ledger.claim_due("gridoracle-single-worker")
    if job is None:
        return False
    try:
        if job.kind == EVALUATE:
            raise JobBlocked("bundle-aware evaluation adapter is not configured")
        from pipeline.scheduler import _run_durable_job

        _run_durable_job(job, engine)
    except Exception as exc:
        ledger.finish(job, "gridoracle-single-worker", exc)
    else:
        ledger.finish(job, "gridoracle-single-worker")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "role", choices=("api", "scheduler", "worker", "check", "ready")
    )
    parser.add_argument("--season", type=int)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    configure()
    if args.role == "ready":
        with urlopen("http://127.0.0.1:8000/ready", timeout=3) as response:
            if response.status != 200:
                raise ValueError("API not ready")
        return
    if args.role == "check":
        if (
            file_digest(Path(os.environ["GRIDORACLE_BUNDLE_FILE"]))
            != os.environ["GRIDORACLE_BUNDLE_SHA256"]
        ):
            raise ValueError("model bundle manifest checksum mismatch")
        if time.time() - Path("/tmp/heartbeat").stat().st_mtime > 1800:
            raise ValueError("runtime heartbeat expired")
        return
    if args.role == "api":
        import uvicorn

        from gridoracle.ops.serving import app

        uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
        return
    if args.role == "scheduler" and args.season is None:
        parser.error("scheduler requires an explicit --season")
    bundle_check()
    engine = create_engine(os.environ["DATABASE_URL"])
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        # Advisory lock lasts for this session and prevents duplicate schedulers
        # or workers even if an operator accidentally scales Compose replicas.
        with engine.connect() as lock:
            key = 13001 if args.role == "scheduler" else 13002
            if not lock.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
            ).scalar_one():
                raise ValueError("runtime role already has an owner")
            while not stopping:
                start = time.monotonic()
                if args.role == "scheduler":
                    scheduler_tick(engine, args.season)
                else:
                    worker_tick(engine)
                Path("/tmp/heartbeat").touch()
                print(
                    json.dumps(
                        {
                            "service": f"gridoracle-{args.role}",
                            "level": "info",
                            "event": "tick",
                            "duration_seconds": time.monotonic() - start,
                        }
                    ),
                    flush=True,
                )
                if args.once:
                    break
                deadline = time.monotonic() + (300 if args.role == "scheduler" else 30)
                while not stopping and time.monotonic() < deadline:
                    time.sleep(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
