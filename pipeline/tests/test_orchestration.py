from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine

from pipeline.orchestration import (
    EVALUATE,
    POST_PUBLISH,
    PRE_FEATURE,
    RESULT_INGEST,
    EventSchedule,
    JobBlocked,
    JobLedger,
    qualifying_publication_ready,
    select_weather_for_interval,
    weekend_graph,
)


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


def event(*, race_id=7, lifecycle="scheduled", sprint=False):
    sessions = {
        "Practice 1": datetime(2026, 3, 13, 10, tzinfo=UTC),
        "Qualifying": datetime(2026, 3, 14, 15, tzinfo=UTC),
        "Race": datetime(2026, 3, 15, 14, tzinfo=UTC),
    }
    if sprint:
        sessions["Sprint Qualifying"] = datetime(2026, 3, 13, 14, tzinfo=UTC)
        sessions["Sprint"] = datetime(2026, 3, 14, 10, tzinfo=UTC)
    return EventSchedule(race_id, 2026, 1, sessions, 20, lifecycle)


def ledger_at(now):
    ledger = JobLedger(create_engine("sqlite://"), Clock(now))
    ledger.reconcile(event())
    return ledger


def drain(ledger):
    ran = []
    handlers = {job.kind: lambda item, kind=job.kind: ran.append(kind) for job in weekend_graph(event())}
    while ledger.run_once("worker-a", handlers):
        pass
    return ran


@pytest.mark.parametrize(
    "now,expected",
    [
        (datetime(2026, 3, 14, 14, 59, tzinfo=UTC), {PRE_FEATURE}),
        (datetime(2026, 3, 14, 16, tzinfo=UTC), {POST_PUBLISH}),
        (datetime(2026, 3, 15, 16, tzinfo=UTC), {RESULT_INGEST, EVALUATE}),
    ],
)
def test_restart_reconciles_before_after_qualifying_and_after_race(now, expected):
    ledger = ledger_at(now)
    ran = set(drain(ledger))
    assert expected <= ran


def test_result_chain_is_independent_of_existing_forecast_publication():
    ledger = ledger_at(datetime(2026, 3, 15, 16, tzinfo=UTC))
    # A prior horizon may already be published; result ingest is not dependent on it.
    with ledger.engine.begin() as conn:
        conn.execute(
            __import__("sqlalchemy").text("UPDATE orchestration_jobs SET status='succeeded' WHERE kind=:kind"),
            {"kind": POST_PUBLISH},
        )
    assert RESULT_INGEST in drain(ledger)


def test_incomplete_qualifying_is_visibly_blocked():
    with pytest.raises(JobBlocked, match="incomplete"):
        qualifying_publication_ready(ingested_entries=19, expected_entries=20, grid_verified=True)
    with pytest.raises(JobBlocked, match="grid_verified=False"):
        qualifying_publication_ready(ingested_entries=20, expected_entries=20, grid_verified=False)


def test_duplicate_workers_claim_only_one_job():
    ledger = ledger_at(datetime(2026, 3, 14, 14, 59, tzinfo=UTC))
    first = ledger.claim_due("one")
    second = ledger.claim_due("two")
    assert first is not None
    assert second is None
    ledger.finish(first, "one")
    assert ledger.status(first.key) == "succeeded"


def test_expired_lease_is_recovered_after_restart():
    clock = Clock(datetime(2026, 3, 14, 14, 59, tzinfo=UTC))
    ledger = JobLedger(create_engine("sqlite://"), clock)
    ledger.reconcile(event())
    job = ledger.claim_due("crashed", timedelta(seconds=1))
    assert job is not None
    clock.value += timedelta(seconds=2)
    assert ledger.recover_expired_leases() == 1
    assert ledger.claim_due("replacement") is not None


def test_revised_calendar_supersedes_pending_jobs_and_rebuilds_snapshot():
    ledger = ledger_at(datetime(2026, 3, 12, tzinfo=UTC))
    revised = event()
    revised = EventSchedule(
        revised.race_id,
        revised.season,
        revised.round_number,
        {**revised.sessions, "Race": datetime(2026, 3, 16, 14, tzinfo=UTC)},
        20,
    )
    ledger.reconcile(revised)
    with ledger.engine.connect() as conn:
        superseded = conn.execute(
            __import__("sqlalchemy").text("SELECT count(*) FROM orchestration_jobs WHERE status='superseded'")
        ).scalar_one()
    assert superseded > 0


def test_sprint_cutoff_uses_first_competitive_timestamp_and_postponed_has_no_jobs():
    sprint_jobs = {job.kind: job for job in weekend_graph(event(sprint=True))}
    assert sprint_jobs[PRE_FEATURE].due_at == datetime(2026, 3, 13, 13, 59, tzinfo=UTC)
    assert weekend_graph(event(lifecycle="postponed")) == []


def test_weather_interval_distinguishes_unavailable_from_dry():
    start = datetime(2026, 3, 15, 14, tzinfo=UTC)
    end = start + timedelta(hours=2)
    assert select_weather_for_interval([], start, end)["availability"] == "unavailable"
    dry = select_weather_for_interval([{"valid_at": start, "rain_probability": 0}], start, end)
    assert dry["availability"] == "available"
    assert dry["rain_probability"] == 0
