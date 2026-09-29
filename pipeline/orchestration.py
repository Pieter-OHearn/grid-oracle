"""Durable, timestamp-driven race-weekend orchestration.

This module deliberately has no scheduler dependency.  A scheduler merely calls
``reconcile`` and ``run_once``; the database ledger is the source of truth, so
restarts and multiple workers cannot turn an in-memory schedule into state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine

UTC_NOW = Callable[[], datetime]

PRE_FEATURE = "pre_weekend.feature"
PRE_PREDICT = "pre_weekend.predict"
PRE_PUBLISH = "pre_weekend.publish"
QUALIFY_INGEST = "post_qualifying.ingest"
POST_FEATURE = "post_qualifying.feature"
POST_PREDICT = "post_qualifying.predict"
POST_PUBLISH = "post_qualifying.publish"
RESULT_INGEST = "result.ingest"
EVALUATE = "result.evaluate"


class JobBlocked(RuntimeError):
    """An eligibility/contract failure that must remain visible to operators."""


@dataclass(frozen=True)
class EventSchedule:
    race_id: int
    season: int
    round_number: int
    sessions: dict[str, datetime]
    expected_entries: int
    lifecycle: str = "scheduled"

    def timestamp(self, name: str) -> datetime:
        for key, value in self.sessions.items():
            if key.casefold() == name.casefold():
                if value.tzinfo is None:
                    raise ValueError("session timestamps must be timezone-aware")
                return value.astimezone(UTC)
        raise JobBlocked(f"missing required {name} timestamp")

    def first_competitive(self) -> datetime:
        ignored = {"practice", "testing"}
        candidates = [
            value.astimezone(UTC)
            for name, value in self.sessions.items()
            if not any(term in name.casefold() for term in ignored)
        ]
        if not candidates:
            raise JobBlocked("calendar has no competitive session timestamp")
        return min(candidates)


@dataclass(frozen=True)
class Job:
    key: str
    race_id: int
    kind: str
    due_at: datetime
    payload: dict[str, Any]


def _key(race_id: int, kind: str) -> str:
    return f"race:{race_id}:{kind}"


def weekend_graph(event: EventSchedule) -> list[Job]:
    """Return the explicit three-chain graph using source session timestamps.

    The pre-weekend deadline is before the first competitive session, not a
    convenient calendar date.  A Grand Prix qualifying session is named
    explicitly, therefore a sprint shootout never unlocks post-qualifying.
    """
    if event.lifecycle in {"cancelled", "postponed"}:
        return []
    pre_cutoff = event.first_competitive() - timedelta(minutes=1)
    qualifying = event.timestamp("Qualifying")
    race = event.timestamp("Race")
    payload = {
        "season": event.season,
        "round": event.round_number,
        "expected_entries": event.expected_entries,
        "schedule_fingerprint": schedule_fingerprint(event),
        "race_start": race.isoformat(),
        "qualifying_start": qualifying.isoformat(),
    }
    specs = (
        (PRE_FEATURE, pre_cutoff, ()),
        (PRE_PREDICT, pre_cutoff, (PRE_FEATURE,)),
        (PRE_PUBLISH, pre_cutoff, (PRE_PREDICT,)),
        (QUALIFY_INGEST, qualifying + timedelta(minutes=45), ()),
        (POST_FEATURE, qualifying + timedelta(minutes=45), (QUALIFY_INGEST,)),
        (POST_PREDICT, qualifying + timedelta(minutes=45), (POST_FEATURE,)),
        (POST_PUBLISH, qualifying + timedelta(minutes=45), (POST_PREDICT,)),
        # Evaluation is purposefully independent of either publication chain.
        (RESULT_INGEST, race + timedelta(minutes=60), ()),
        (EVALUATE, race + timedelta(minutes=60), (RESULT_INGEST,)),
    )
    return [
        Job(
            key=_key(event.race_id, kind),
            race_id=event.race_id,
            kind=kind,
            due_at=due,
            payload={**payload, "depends_on": [_key(event.race_id, dep) for dep in dependencies]},
        )
        for kind, due, dependencies in specs
    ]


def schedule_fingerprint(event: EventSchedule) -> str:
    material = {
        "lifecycle": event.lifecycle,
        "sessions": sorted((name, value.astimezone(UTC).isoformat()) for name, value in event.sessions.items()),
        "expected_entries": event.expected_entries,
    }
    return hashlib.sha256(json.dumps(material, separators=(",", ":")).encode()).hexdigest()


class JobLedger:
    """A persistent, lease-based single-writer ledger usable on SQLite/Postgres."""

    def __init__(self, engine: Engine, now: UTC_NOW = lambda: datetime.now(UTC)):
        self.engine, self.now = engine, now

    def initialize(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS orchestration_jobs (
                  job_key VARCHAR(220) PRIMARY KEY, race_id INTEGER NOT NULL,
                  kind VARCHAR(80) NOT NULL, due_at TIMESTAMP NOT NULL,
                  payload JSON NOT NULL, status VARCHAR(20) NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0, lease_owner VARCHAR(100),
                  lease_until TIMESTAMP, last_error TEXT, completed_at TIMESTAMP,
                  created_at TIMESTAMP NOT NULL, updated_at TIMESTAMP NOT NULL
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS orchestration_job_dependencies (
                  job_key VARCHAR(220) NOT NULL, dependency_key VARCHAR(220) NOT NULL,
                  PRIMARY KEY (job_key, dependency_key)
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS orchestration_calendar_revisions (
                  race_id INTEGER NOT NULL, fingerprint VARCHAR(64) NOT NULL,
                  observed_at TIMESTAMP NOT NULL, payload JSON NOT NULL,
                  PRIMARY KEY (race_id, fingerprint)
                )
            """)
            )

    def reconcile(self, event: EventSchedule) -> None:
        """Upsert a graph and supersede pending jobs when a calendar changes."""
        self.initialize()
        now = self.now()
        fingerprint = schedule_fingerprint(event)
        graph = weekend_graph(event)
        with self.engine.begin() as conn:
            old = conn.execute(
                text("SELECT fingerprint FROM orchestration_calendar_revisions WHERE race_id=:race_id"),
                {"race_id": event.race_id},
            ).fetchall()
            if old and all(row[0] != fingerprint for row in old):
                conn.execute(
                    text(
                        "UPDATE orchestration_jobs SET status='superseded', "
                        "updated_at=:now WHERE race_id=:race_id "
                        "AND status='pending'"
                    ),
                    {"race_id": event.race_id, "now": now},
                )
            conn.execute(
                text("""INSERT INTO orchestration_calendar_revisions (race_id, fingerprint, observed_at, payload)
                VALUES (:race_id, :fingerprint, :observed_at, :payload)
                ON CONFLICT (race_id, fingerprint) DO NOTHING"""),
                {
                    "race_id": event.race_id,
                    "fingerprint": fingerprint,
                    "observed_at": now,
                    "payload": json.dumps(event.sessions, default=lambda value: value.isoformat()),
                },
            )
            for job in graph:
                conn.execute(
                    text("""INSERT INTO orchestration_jobs
                    (job_key, race_id, kind, due_at, payload, status, attempts, created_at, updated_at)
                    VALUES (:job_key,:race_id,:kind,:due_at,:payload,'pending',0,:now,:now)
                    ON CONFLICT (job_key) DO NOTHING"""),
                    {
                        "job_key": job.key,
                        "race_id": job.race_id,
                        "kind": job.kind,
                        "due_at": job.due_at,
                        "payload": json.dumps(job.payload),
                        "now": now,
                    },
                )
                for dependency in job.payload["depends_on"]:
                    conn.execute(
                        text("""INSERT INTO orchestration_job_dependencies (job_key, dependency_key)
                        VALUES (:job_key,:dependency_key) ON CONFLICT DO NOTHING"""),
                        {"job_key": job.key, "dependency_key": dependency},
                    )

    def claim_due(self, worker: str, lease_for: timedelta = timedelta(minutes=5)) -> Job | None:
        now = self.now()
        with self.engine.begin() as conn:
            while row := conn.execute(
                text("""SELECT j.job_key, j.race_id, j.kind, j.due_at, j.payload
                FROM orchestration_jobs j
                WHERE j.status='pending' AND j.due_at <= :now
                AND NOT EXISTS (
                  SELECT 1 FROM orchestration_job_dependencies d
                  JOIN orchestration_jobs p ON p.job_key=d.dependency_key
                  WHERE d.job_key=j.job_key AND p.status != 'succeeded'
                )
                ORDER BY j.due_at, j.job_key LIMIT 1"""),
                {"now": now},
            ).fetchone():
                payload = json.loads(row[4]) if isinstance(row[4], str) else row[4]
                qualifying_at = datetime.fromisoformat(payload["qualifying_start"].replace("Z", "+00:00"))
                if row[2].startswith("pre_weekend.") and now >= qualifying_at:
                    conn.execute(
                        text("""UPDATE orchestration_jobs SET status='blocked',
                        last_error='pre-weekend cutoff elapsed before execution',
                        updated_at=:now WHERE job_key=:job_key"""),
                        {"now": now, "job_key": row[0]},
                    )
                    continue
                updated = conn.execute(
                    text("""UPDATE orchestration_jobs SET status='running', attempts=attempts+1,
                lease_owner=:worker, lease_until=:lease_until, updated_at=:now
                WHERE job_key=:job_key AND status='pending'"""),
                    {"worker": worker, "lease_until": now + lease_for, "now": now, "job_key": row[0]},
                ).rowcount
                if updated == 1:
                    return Job(row[0], row[1], row[2], row[3], payload)
            return None

    def recover_expired_leases(self) -> int:
        now = self.now()
        with self.engine.begin() as conn:
            return conn.execute(
                text("""UPDATE orchestration_jobs SET status='pending', lease_owner=NULL, lease_until=NULL,
                updated_at=:now, last_error='lease expired; reconciled for retry'
                WHERE status='running' AND lease_until < :now"""),
                {"now": now},
            ).rowcount

    def finish(self, job: Job, worker: str, error: Exception | None = None, max_attempts: int = 4) -> None:
        now = self.now()
        if error is None:
            status, message = "succeeded", None
        elif isinstance(error, JobBlocked) or self.attempts(job.key) >= max_attempts:
            status, message = "blocked", str(error)
        else:
            status, message = "pending", str(error)
        with self.engine.begin() as conn:
            conn.execute(
                text("""UPDATE orchestration_jobs SET status=:status, lease_owner=NULL, lease_until=NULL,
                last_error=:message, completed_at=:completed_at, updated_at=:now
                WHERE job_key=:job_key AND status='running' AND lease_owner=:worker"""),
                {
                    "status": status,
                    "message": message,
                    "completed_at": now if status == "succeeded" else None,
                    "now": now,
                    "job_key": job.key,
                    "worker": worker,
                },
            )

    def attempts(self, job_key: str) -> int:
        with self.engine.connect() as conn:
            return int(
                conn.execute(
                    text("SELECT attempts FROM orchestration_jobs WHERE job_key=:job_key"), {"job_key": job_key}
                ).scalar_one()
            )

    def status(self, job_key: str) -> str:
        with self.engine.connect() as conn:
            return str(
                conn.execute(
                    text("SELECT status FROM orchestration_jobs WHERE job_key=:job_key"), {"job_key": job_key}
                ).scalar_one()
            )

    def run_once(self, worker: str, handlers: dict[str, Callable[[Job], None]]) -> bool:
        self.recover_expired_leases()
        job = self.claim_due(worker)
        if job is None:
            return False
        try:
            handlers[job.kind](job)
        except Exception as exc:  # provider failures become visible ledger state
            self.finish(job, worker, exc)
        else:
            self.finish(job, worker)
        return True


def qualifying_publication_ready(*, ingested_entries: int, expected_entries: int, grid_verified: bool) -> None:
    """The explicit gate before a post-qualifying publish handler may publish."""
    if not grid_verified or ingested_entries != expected_entries:
        raise JobBlocked(
            f"qualifying field incomplete: {ingested_entries}/{expected_entries}; grid_verified={grid_verified}"
        )


def select_weather_for_interval(records: Iterable[dict[str, Any]], start: datetime, end: datetime) -> dict[str, Any]:
    """Select weather overlapping the race interval; unknown is never rewritten dry."""
    matches = [record for record in records if start <= record["valid_at"].astimezone(UTC) <= end]
    if not matches:
        return {"availability": "unavailable", "rain_probability": None}
    rainy = max(matches, key=lambda record: record.get("rain_probability") or 0)
    return {"availability": "available", **rainy}
