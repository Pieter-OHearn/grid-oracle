"""Bounded synthetic ledger backfill measurement; no provider/model execution."""

import importlib
import json
import os
import resource
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine

from gridoracle.ops.runtime import configure
from pipeline.orchestration import EventSchedule, JobLedger


def main():
    libraries = {
        name: importlib.import_module(name).__version__
        for name in ("xgboost", "pyarrow", "sklearn")
    }
    configure()
    engine = create_engine(os.environ["DATABASE_URL"])
    now = datetime(2022, 5, 1, tzinfo=UTC)
    ledger = JobLedger(engine, now=lambda: now + timedelta(days=1, hours=23))
    timings = []
    try:
        for revision in range(24):
            shift = timedelta(hours=revision)
            event = EventSchedule(
                race_id=2022,
                season=2022,
                round_number=1,
                expected_entries=22,
                sessions={
                    "Qualifying": now + timedelta(days=2) + shift,
                    "Race": now + timedelta(days=3) + shift,
                },
            )
            start = time.monotonic()
            ledger.reconcile(event)
            timings.append(time.monotonic() - start)
        # Prove single-claim exclusion while the first lease is active. Work
        # handlers are not invoked: the production publication adapter is absent.
        first = ledger.claim_due("benchmark-one")
        second = ledger.claim_due("benchmark-two")
        if first is None or second is not None:
            raise ValueError("single-event backfill lease exclusion failed")
        ledger.finish(first, "benchmark-one")
        print(
            json.dumps(
                {
                    "mode": "synthetic-ledger-only",
                    "native_libraries": libraries,
                    "revisions": 24,
                    "events_concurrent": 1,
                    "provider_requests": 0,
                    "reconcile_p95_seconds": sorted(timings)[22],
                    "reconcile_max_seconds": max(timings),
                    "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    / 1024,
                    "backfill_limit": "one event / one worker; "
                    "production prediction adapter remains blocked",
                }
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
