"""A live weekend on real PostgreSQL: install, issue, evaluate, back up, restore.

Recorded 2026 Jolpica payloads stand in for the provider, released by a fake
clock as the real API would publish them. Skipped without WP15_POSTGRES_URL
(an empty PostgreSQL 16 superuser URL) and WP15_POSTGRES_CONTAINER (its
container, for pg_dump and pg_restore of the matching version).
"""

import json
import os
import subprocess
import uuid
from datetime import UTC, datetime

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session

from gridoracle.ops import backup as backups
from gridoracle.ops.bundle import verify_bundle, verify_selection
from gridoracle.ops.production_bundle import register, write
from gridoracle.ops.roles import READ, WRITE, apply
from gridoracle.ops.runtime import MAINTENANCE_LOCK
from pipeline.issuance.adapter import ProductionIssuance
from pipeline.issuance.jolpica import JolpicaClient
from pipeline.orchestration import Job, JobLedger
from pipeline.tests.jolpica_fixture import FakeJolpica
from scripts.wp13_migrate import migrate
from scripts.wp13_recovery import compare, seal

WORKER_IMAGE = "ghcr.io/pieter-ohearn/gridoracle-worker:v0.0.0@sha256:" + "a" * 64


@pytest.fixture(autouse=True)
def no_provider_network(monkeypatch):
    def deny(*_args, **_kwargs):
        raise AssertionError("live provider network is forbidden in tests")

    monkeypatch.setattr(requests.sessions.Session, "request", deny)


@pytest.fixture
def container():
    name = os.getenv("WP15_POSTGRES_CONTAINER")
    if not os.getenv("WP15_POSTGRES_URL") or not name:
        pytest.skip("WP15_POSTGRES_URL/CONTAINER missing; PostgreSQL NOT exercised")
    return name


def _dump_with(container):
    def dump(url, target):
        from sqlalchemy.engine import make_url

        database = make_url(url).database
        target.write_bytes(
            subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "pg_dump",
                    "-U",
                    "postgres",
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    database,
                ],
                check=True,
                capture_output=True,
            ).stdout
        )

    return dump


@pytest.fixture
def deployment(container, tmp_path, monkeypatch):
    """A fresh installation exactly as the runbook builds it."""
    url = os.environ["WP15_POSTGRES_URL"]
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    suffix = uuid.uuid4().hex[:12]
    database = f"wp15_{suffix}"
    api_role, worker_role = f"wp15_api_{suffix}", f"wp15_worker_{suffix}"
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {database}"))
    engine = create_engine(admin.url.set(database=database))
    monkeypatch.setattr(backups, "_dump", _dump_with(container))
    artifacts = tmp_path / "artifacts"
    bundles = tmp_path / "bundles"
    artifacts.mkdir()
    bundles.mkdir()
    try:
        # 1. The bundle file and closure, before any schema exists.
        digest = write(artifacts, bundles, WORKER_IMAGE, "test-revision")
        bundle_file = bundles / f"{digest}.json"
        monkeypatch.setenv("DATABASE_URL", str(engine.url.render_as_string(False)))
        monkeypatch.setenv("GRIDORACLE_ARTIFACT_ROOT", str(artifacts))
        monkeypatch.setenv("GRIDORACLE_BUNDLE_FILE", str(bundle_file))
        monkeypatch.setenv("GRIDORACLE_BUNDLE_SHA256", digest)
        # 2. A sealed backup of the empty database, then the explicit migration.
        empty = tmp_path / "empty-backup"
        empty.mkdir()
        backups._dump(str(engine.url), empty / "database.dump")
        receipt = seal(empty, artifacts, bundle_file, digest)
        migrate(empty, receipt, bootstrap_empty=True)
        # 3. Roles from the URL secrets, then the bundle's manifests.
        apply(
            engine,
            [
                (str(engine.url.set(username=api_role, password="api-secret")), READ),
                (
                    str(engine.url.set(username=worker_role, password="worker-secret")),
                    WRITE,
                ),
            ],
        )
        register(engine, artifacts, bundle_file, digest)
        bundle = verify_bundle(artifacts, bundle_file, digest)
        yield {
            "engine": engine,
            "admin": admin,
            "artifacts": artifacts,
            "bundle": bundle,
            "bundle_file": bundle_file,
            "digest": digest,
            "api": engine.url.set(username=api_role, password="api-secret"),
            "worker": engine.url.set(username=worker_role, password="worker-secret"),
            "tmp": tmp_path,
            "container": container,
        }
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE {database} WITH (FORCE)"))
            for role in (api_role, worker_role):
                conn.execute(text(f"DROP ROLE IF EXISTS {role}"))
        admin.dispose()


class Weekend:
    def __init__(self, deployment, start):
        self.clock = {"now": start}
        self.session = FakeJolpica(lambda: self.clock["now"])
        worker = create_engine(deployment["worker"])
        self.engine = worker
        self.issuance = ProductionIssuance(
            worker,
            deployment["artifacts"],
            deployment["bundle"],
            JolpicaClient(
                deployment["tmp"] / "provider",
                session=self.session,
                now=lambda: self.clock["now"],
            ),
            now=lambda: self.clock["now"],
        )
        self.ledger = JobLedger(worker, now=lambda: self.clock["now"])

    def at(self, value):
        self.clock["now"] = value
        return self

    def reconcile(self):
        schedules = self.issuance.reconcile(2026)
        for schedule in schedules:
            self.ledger.reconcile(schedule)
        return schedules

    def drain(self):
        for _ in range(40):
            if not self.ledger.run_once("test-worker", self.issuance.handlers(), 40):
                return
        raise AssertionError("unbounded drain")

    def jobs(self):
        with self.engine.connect() as conn:
            return dict(
                conn.execute(
                    text("SELECT kind, status FROM orchestration_jobs WHERE race_id=3")
                ).fetchall()
            )


def _public(url, path):
    from api.database import get_db
    from api.main import create_app

    engine = create_engine(url)
    app = create_app(legacy=False)

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            response = client.get(path)
            assert response.status_code == 200, response.text
            return response.json()
    finally:
        engine.dispose()


def test_a_live_weekend_publishes_both_horizons_and_evaluates(deployment):
    weekend = Weekend(deployment, datetime(2026, 3, 26, 12, tzinfo=UTC))
    schedules = weekend.reconcile()
    # Rounds 1 and 2 are caught up; only round 3 can open its field yet.
    assert [schedule.round_number for schedule in schedules] == [3]
    assert schedules[0].expected_entries == 22
    with weekend.engine.connect() as conn:
        completed = (
            conn.execute(
                text(
                    "SELECT round FROM races WHERE season=2026 AND is_completed "
                    "ORDER BY round"
                )
            )
            .scalars()
            .all()
        )
    assert completed == [1, 2]

    weekend.at(datetime(2026, 3, 27, 6, tzinfo=UTC)).drain()
    assert weekend.jobs()["pre_weekend.publish"] == "succeeded"

    # Qualifying is due 45 minutes after its start but published after an hour.
    weekend.at(datetime(2026, 3, 28, 6, 45, tzinfo=UTC)).drain()
    assert weekend.jobs()["post_qualifying.ingest"] == "pending"
    weekend.at(datetime(2026, 3, 28, 7, 5, tzinfo=UTC)).drain()
    assert weekend.jobs()["post_qualifying.publish"] == "succeeded"

    weekend.at(datetime(2026, 3, 29, 6, 5, tzinfo=UTC)).drain()
    jobs = weekend.jobs()
    assert set(jobs.values()) == {"succeeded"}, jobs

    with weekend.engine.connect() as conn:
        published = (
            conn.execute(
                text(
                    "SELECT horizon FROM forecast_publications WHERE race_id=3 "
                    "ORDER BY horizon"
                )
            )
            .scalars()
            .all()
        )
        evaluations = conn.execute(
            text("SELECT count(*) FROM evaluation_runs")
        ).scalar_one()
        grades = (
            conn.execute(text("SELECT DISTINCT provenance_grade FROM forecast_runs"))
            .scalars()
            .all()
        )
    assert published == ["post_qualifying", "pre_weekend"]
    assert evaluations == 2
    assert grades == ["observed"]

    # The API reader serves both horizons with dated names, and the scorecard.
    for horizon in ("pre_weekend", "post_qualifying"):
        forecast = _public(
            deployment["api"],
            f"/api/v1/seasons/2026/events/3/forecast?horizon={horizon}",
        )
        text_dump = json.dumps(forecast)
        assert "Verstappen" in text_dump or "Russell" in text_dump
        performance = _public(
            deployment["api"],
            f"/api/v1/seasons/2026/events/3/performance?horizon={horizon}",
        )
        assert performance["status"] == "stored_evaluation"

    # Readiness: the bundle's lineage is still bound in the database.
    verify_selection(weekend.engine, deployment["bundle"])

    # A retried handler replays its stored inputs instead of conflicting.
    with weekend.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT job_key, race_id, kind, due_at, payload "
                "FROM orchestration_jobs "
                "WHERE race_id=3 "
                "AND kind IN ('pre_weekend.feature', 'pre_weekend.predict')"
            )
        ).fetchall()
        runs = conn.execute(text("SELECT count(*) FROM forecast_runs")).scalar_one()
    for row in rows:
        payload = (
            row.payload if isinstance(row.payload, dict) else json.loads(row.payload)
        )
        weekend.issuance.handlers()[row.kind](
            Job(row.job_key, row.race_id, row.kind, row.due_at, payload)
        )
    with weekend.engine.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM forecast_runs")).scalar_one()
            == runs
        )
    weekend.engine.dispose()


def test_the_reader_cannot_write_and_issued_history_is_immutable(deployment):
    weekend = Weekend(deployment, datetime(2026, 3, 26, 12, tzinfo=UTC))
    weekend.reconcile()
    weekend.at(datetime(2026, 3, 27, 6, tzinfo=UTC)).drain()
    reader = create_engine(deployment["api"])
    try:
        with (
            pytest.raises(ProgrammingError, match="permission denied"),
            reader.begin() as conn,
        ):
            conn.execute(text("UPDATE races SET name='x' WHERE id=3"))
        with (
            pytest.raises(ProgrammingError, match="permission denied"),
            weekend.engine.begin() as conn,
        ):
            conn.execute(text("CREATE TABLE intruder (id int)"))
        with (
            pytest.raises(DBAPIError, match="immutable provenance"),
            weekend.engine.begin() as conn,
        ):
            conn.execute(text("UPDATE forecast_entry_outputs SET output_sha256='x'"))
    finally:
        reader.dispose()
        weekend.engine.dispose()


def test_backup_waits_for_writers_and_restores_into_a_new_database(deployment):
    weekend = Weekend(deployment, datetime(2026, 3, 26, 12, tzinfo=UTC))
    weekend.reconcile()
    weekend.at(datetime(2026, 3, 27, 6, tzinfo=UTC)).drain()
    engine = deployment["engine"]

    # A writer holding the gate blocks the backup's exclusive lock.
    with engine.connect() as writer, engine.connect() as probe:
        writer.execute(
            text("SELECT pg_advisory_lock_shared(:k)"), {"k": MAINTENANCE_LOCK}
        )
        assert not probe.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": MAINTENANCE_LOCK}
        ).scalar_one()
        writer.execute(
            text("SELECT pg_advisory_unlock_shared(:k)"), {"k": MAINTENANCE_LOCK}
        )

    root = deployment["tmp"] / "backups"
    root.mkdir()
    assert backups.run(root, keep=2)
    assert backups.healthy(root)
    status = json.loads((root / "status/status.json").read_text())
    assert status["verified_sets"] == 1 and status["failed_sets"] == 0
    name = status["last_set"]
    receipt = (root / "receipts" / f"{name}.sha256").read_text().strip()
    assert receipt == status["last_receipt_sha256"]

    # Restore drill: a new database from the set, compared by hashes.
    restored = f"{engine.url.database}_restore"
    admin = deployment["admin"]
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {restored}"))
    target = create_engine(engine.url.set(database=restored))
    try:
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                deployment["container"],
                "pg_restore",
                "-U",
                "postgres",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                "-d",
                restored,
            ],
            input=(root / "sets" / name / "database.dump").read_bytes(),
            capture_output=True,
            check=True,
        )
        live = root / "sets" / name
        compare(
            target,
            live,
            receipt,
            live / "artifacts",
            live / "bundle.json",
            deployment["digest"],
        )
        # A tampered set is refused, and a second run keeps two sets at most.
        assert backups.run(root, keep=2) and backups.run(root, keep=2)
        assert len(list((root / "sets").iterdir())) == 2
        newest = sorted((root / "sets").iterdir())[-1]
        (newest / "database.dump").write_bytes(b"tamper")
        verified, failed = backups.verify_all(root)
        assert (verified, failed) == (1, 1)
        assert not backups.run(root, keep=5)
        assert not backups.healthy(root)
    finally:
        target.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE {restored} WITH (FORCE)"))
        weekend.engine.dispose()
