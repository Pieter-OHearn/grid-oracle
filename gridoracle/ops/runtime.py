"""Separate HTTP, reconciliation, and bounded execution entry points."""

import argparse
import json
import os
import signal
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, text

from gridoracle.ops.bundle import file_digest, verify_bundle

# A coordinated backup takes this advisory lock exclusively; every scheduler
# and worker tick holds it shared, so a backup waits for running ticks and no
# new tick starts until the recovery set is sealed.
MAINTENANCE_LOCK = 13010
# The live calendar is read at most this often (Jolpica's hourly budget).
CALENDAR_SECONDS = 6 * 3600
# Provider lateness is retried for about nine hours before a job blocks.
PROVIDER_ATTEMPTS = 40


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


@contextmanager
def writer_gate(engine):
    """Hold the maintenance lock shared for one tick (PostgreSQL only)."""
    if engine.dialect.name != "postgresql":
        yield
        return
    with engine.connect() as conn:
        conn.execute(
            text("SELECT pg_advisory_lock_shared(:key)"), {"key": MAINTENANCE_LOCK}
        )
        try:
            yield
        finally:
            conn.execute(
                text("SELECT pg_advisory_unlock_shared(:key)"),
                {"key": MAINTENANCE_LOCK},
            )


def provider_client():
    from pipeline.issuance.jolpica import JolpicaClient

    return JolpicaClient(Path(os.getenv("GRIDORACLE_PROVIDER_ROOT", "/tmp/provider")))


def scheduler_tick(engine, season: int, issuance, *, sync: bool) -> None:
    from pipeline.orchestration import JobLedger

    ledger = JobLedger(engine)
    ledger.recover_expired_leases(PROVIDER_ATTEMPTS)
    if not sync:
        return
    for schedule in issuance.reconcile(season):
        ledger.reconcile(schedule)


def worker_tick(engine, issuance) -> bool:
    from pipeline.orchestration import JobLedger

    return JobLedger(engine).run_once(
        "gridoracle-single-worker", issuance.handlers(), PROVIDER_ATTEMPTS
    )


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
    bundle = bundle_check()
    engine = create_engine(os.environ["DATABASE_URL"])
    from pipeline.issuance.adapter import ProductionIssuance

    issuance = ProductionIssuance(
        engine, Path(os.environ["GRIDORACLE_ARTIFACT_ROOT"]), bundle, provider_client()
    )
    stopping = False
    synced_at = 0.0

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
                with writer_gate(engine):
                    if args.role == "scheduler":
                        sync = start - synced_at >= CALENDAR_SECONDS or not synced_at
                        try:
                            scheduler_tick(engine, args.season, issuance, sync=sync)
                        except Exception as error:
                            # A provider outage is logged and retried next tick.
                            print(
                                json.dumps(
                                    {
                                        "service": "gridoracle-scheduler",
                                        "level": "error",
                                        "event": "calendar",
                                        "error": type(error).__name__,
                                    }
                                ),
                                flush=True,
                            )
                        else:
                            synced_at = start if sync else synced_at
                    else:
                        while worker_tick(engine, issuance) and not stopping:
                            pass
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
