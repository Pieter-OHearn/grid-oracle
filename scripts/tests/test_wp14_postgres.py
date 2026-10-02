"""Real PostgreSQL integration checks. Explicitly skipped outside WP14 CI."""

import inspect
import json
import os
import shutil
import subprocess
import textwrap
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta

import pytest
import requests
from sqlalchemy import create_engine, text

from gridoracle.ops.bundle import verify_bundle, verify_selection
from gridoracle.ops.recovery import inventory, schema_revision
from gridoracle.provenance import ForecastEntry, ProvenanceError
from pipeline.benchmark import baselines
from pipeline.benchmark.temporal import TemporalViolation, validate_features
from pipeline.ingest.provider import ProviderAdapter, require_keys
from pipeline.orchestration import (
    JobBlocked,
    JobLedger,
    qualifying_publication_ready,
    weekend_graph,
)
from scripts.regression.replay import (
    RecordedSession,
    WeekendReplay,
    checked_fixtures,
    initialize_legacy,
    recordings,
    time,
)
from scripts.wp13_recovery import compare, seal


@pytest.fixture(autouse=True)
def no_provider_network(monkeypatch):
    def deny(*_args, **_kwargs):
        raise AssertionError(
            "live provider network forbidden in deterministic regression"
        )

    monkeypatch.setattr(requests.sessions.Session, "request", deny)


@pytest.fixture(autouse=True)
def intentional_mutation(monkeypatch):
    """Compile one exact known defect in-process, only on opt-in run."""
    mutant = os.getenv("WP14_MUTANT")
    if not mutant:
        return
    from gridoracle.ops import recovery
    from gridoracle.provenance import store as storage
    from scripts.regression import replay as replay_module

    choices = {
        "partial-publication": (
            storage.ImmutableProvenanceStore,
            "publish",
            'if count != run["expected_entry_count"]:',
            "if False:",
        ),
        "future-availability": (
            storage.ForecastRunInput,
            "validate",
            "if available is not None and cutoff is not None and available > cutoff:",
            "if False:",
        ),
        "tie-advantage": (
            baselines,
            "predict",
            'rank(method="average")',
            'rank(method="first")',
        ),
        "unchecked-output-hash": (
            recovery,
            "inventory",
            'if digest(output) != row["output_sha256"]:',
            "if False:",
        ),
        "future-live-qualifying": (
            replay_module.WeekendReplay,
            "predict",
            "    field = Field(",
            "    if horizon == 'post_qualifying':\n"
            "        with self.engine.connect() as conn:\n"
            "            for index in frame.index:\n"
            "                frame.at[index, 'qualifying_position'] = conn.execute(\n"
            "                    text('SELECT grid_position FROM qualifying_results "
            "WHERE race_id=:race AND driver_id=:driver'),\n"
            "                    {'race': self.race_id, 'driver': "
            "int(frame.at[index, 'driver_identity_key'].split(':')[1]) % 100},\n"
            "                ).scalar_one()\n"
            "    field = Field(",
        ),
        "recaptured-snapshot": (
            replay_module.WeekendReplay,
            "snapshot",
            "if existing is not None:",
            "if False:",
        ),
    }
    owner, name, before, after = choices[mutant]
    function = getattr(owner, name)
    source = textwrap.dedent(inspect.getsource(function))
    assert source.count(before) == 1, "mutation drift: expected exact guard"
    namespace = dict(function.__globals__)
    exec(
        compile(source.replace(before, after), f"<WP14 mutant {mutant}>", "exec"),
        namespace,
    )
    monkeypatch.setattr(owner, name, namespace[name])
    if mutant == "tie-advantage":
        from pipeline.selection import interface

        monkeypatch.setattr(interface, "baseline_predict", namespace[name])


@pytest.fixture
def empty_postgres():
    url = os.getenv("WP14_POSTGRES_URL")
    if not url:
        pytest.skip("WP14_POSTGRES_URL missing; PostgreSQL lifecycle NOT exercised")
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    database = "wp14_" + uuid.uuid4().hex
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {database}"))
    engine = create_engine(admin.url.set(database=database))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE {database} WITH (FORCE)"))
        admin.dispose()


@pytest.fixture
def engine(empty_postgres):
    initialize_legacy(empty_postgres)
    return empty_postgres


def test_unknown_postgresql_schema_is_refused_without_reset(empty_postgres):
    from scripts.db_migrate import DatabaseMigrationError, upgrade_database

    with empty_postgres.begin() as conn:
        conn.execute(text("CREATE TABLE unknown_sentinel (id integer)"))
        conn.execute(text("INSERT INTO unknown_sentinel VALUES (42)"))
    with pytest.raises(DatabaseMigrationError, match="refusing"):
        upgrade_database(str(empty_postgres.url))
    with empty_postgres.connect() as conn:
        assert conn.execute(text("SELECT id FROM unknown_sentinel")).scalar_one() == 42


@pytest.fixture
def replay(engine, tmp_path):
    return WeekendReplay(engine, tmp_path)


def test_recorded_provider_contracts_have_pinned_attribution(tmp_path):
    fixture, manifest = checked_fixtures()
    assert fixture["synthetic"] is True
    assert manifest["license"] == "CC BY-NC-SA 4.0"
    bodies = recordings(tmp_path)
    result = bodies["2022-results-0.json"][0]
    qualifying = bodies["2022-qualifying-0.json"][0]
    assert result["season"] == qualifying["season"] == "2022"
    assert result["round"] == qualifying["round"] == "1"
    assert result["Results"][0]["Driver"]["driverId"] == "leclerc"
    assert qualifying["QualifyingResults"][0]["position"] == "1"


def test_migration_populated_legacy_repeat_and_unknown_refusal(engine):
    assert schema_revision(engine) == "20260929_05"
    with engine.connect() as conn:
        assert (
            conn.execute(text("SELECT full_name FROM drivers WHERE id=99")).scalar_one()
            == "Legacy sentinel"
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM forecast_publications")
            ).scalar_one()
            == 0
        )


def test_every_lifecycle_stage_persists_and_is_public(replay):
    replay.complete()
    assert set(replay.runs) == {"pre_weekend", "post_qualifying"}
    with replay.engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM orchestration_jobs WHERE status='succeeded'")
            ).scalar_one()
            == 9
        )
        assert (
            conn.execute(text("SELECT count(*) FROM qualifying_results")).scalar_one()
            == 22
        )
        assert (
            conn.execute(text("SELECT count(*) FROM race_results")).scalar_one() == 22
        )
        assert (
            conn.execute(text("SELECT count(*) FROM evaluation_runs")).scalar_one() == 2
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM forecast_publications")
            ).scalar_one()
            == 2
        )
        assert (
            conn.execute(
                text("SELECT grid_position FROM race_results WHERE driver_id=20")
            ).scalar_one()
            == 0
        )
    for horizon in replay.runs:
        public = replay.public(horizon)
        assert public["state"] == "published"
        assert public["run"]["run_id"] == replay.runs[horizon]
        assert len(public["run"]["entries"]) == 22
        assert sum(
            e["win_probability"] for e in public["run"]["entries"]
        ) == pytest.approx(1)

        def reproduce(_manifest, horizon=horizon):
            replay.predict(horizon, persist=False)
            return {entry.entry_key: entry.output for entry in replay.outputs[horizon]}

        replay.store.verify_reproduction(replay.runs[horizon], reproduce)
    with replay.client() as client:
        response = client.get(
            "/api/v1/seasons/2026/events/2026/performance?horizon=pre_weekend"
        )
        assert response.status_code == 200, response.text
        assert (
            "3.091042" in response.text
        )  # log(22), computed rather than fixture score


def test_season_opening_ties_never_favor_identity(replay):
    replay.drain()
    values = list(replay.predictions["pre_weekend"]["winner"].values())
    assert len(values) == 22
    assert all(p == pytest.approx(1 / 22, abs=1e-14) for p in values)


def test_partial_publish_keeps_last_good(replay):
    replay.drain()
    saved = replay.public()
    staged = replay.store.create_forecast_run(
        replace(
            replay.inputs["pre_weekend"],
            horizon="post_qualifying",
            idempotency_key="partial",
        )
    )
    replay.store.add_entry_outputs(
        staged, [ForecastEntry("entry:202601", {"win_probability": 1})]
    )
    with pytest.raises(ProvenanceError, match="incomplete field"):
        replay.store.publish(staged, published_at=replay.now)
    assert replay.public() == saved
    assert replay.public("post_qualifying")["state"] == "unavailable"


def test_future_availability_is_rejected(replay):
    replay.drain()
    old = replay.inputs["pre_weekend"]
    with pytest.raises(ProvenanceError, match="availability"):
        replay.store.create_forecast_run(
            replace(
                old,
                idempotency_key="future",
                source_available_at=old.input_cutoff_at + timedelta(seconds=1),
            )
        )


def test_future_sources_results_and_newer_model_cannot_change_issued_forecast(replay):
    replay.complete()
    expected_predictions = dict(replay.predictions)
    saved = replay.public()
    before = {k: v for k, v in replay.hashes().items() if k.startswith("forecast_")}
    replay.fixture["entries"][0]["standings"] = 22
    replay.fixture["entries"][0]["qualifying"] = 22
    with replay.engine.begin() as conn:
        conn.execute(
            text("UPDATE qualifying_results SET grid_position=22 WHERE driver_id=1")
        )
        conn.execute(
            text(
                "INSERT INTO model_versions (id,name,trained_at,training"
                "_races_count) VALUES (99,'newest invalid','2030-01-01',"
                "999)"
            )
        )
    replay.now = time("2026-05-05T16:00:00+00:00")
    raw = replay._artifact("providers/future", replay.fixture)
    replay.store.record_raw_snapshot(
        snapshot_id="future",
        provider="synthetic future",
        retrieved_at=replay.now,
        source_available_at=replay.now,
        **raw,
    )
    replay.result(correction=True)
    replay.evaluate()
    prior_post = replay.public("post_qualifying")
    for horizon in replay.runs:

        def reproduce(_manifest, horizon=horizon):
            prediction = replay.predict(horizon, persist=False)
            assert prediction["order"] == expected_predictions[horizon]["order"]
            assert prediction["winner"] == pytest.approx(
                expected_predictions[horizon]["winner"], abs=1e-14
            )
            return {entry.entry_key: entry.output for entry in replay.outputs[horizon]}

        replay.store.verify_reproduction(replay.runs[horizon], reproduce)
    assert replay.public("post_qualifying") == prior_post
    assert replay.public() == saved
    assert {
        k: v for k, v in replay.hashes().items() if k.startswith("forecast_")
    } == before
    with replay.engine.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM evaluation_runs")).scalar_one() == 4
        )


def test_outage_retry_quarantine_and_last_good(replay):
    replay.drain()
    saved = replay.public()
    session = RecordedSession({"entries": []}, failures=2)
    sleeps = []
    adapter = ProviderAdapter(
        "fixture",
        "WP14",
        replay.root / "outage",
        sleep=sleeps.append,
        random_source=lambda: 0,
    )
    payload, _ = adapter.fetch_json(
        "https://recorded.invalid",
        validator=require_keys("entries"),
        session=session,
        attempts=3,
    )
    assert payload == {"entries": []} and session.calls == 3 and sleeps == [0.5, 1.0]
    with pytest.raises(requests.Timeout):
        adapter.fetch_json(
            "https://recorded.invalid",
            validator=require_keys("entries"),
            session=RecordedSession({}, failures=4),
            attempts=2,
        )
    assert list((replay.root / "outage/quarantine").glob("*.json"))
    assert replay.public() == saved


@pytest.mark.parametrize(
    "stage",
    [
        "post_qualifying.ingest",
        "post_qualifying.feature",
        "post_qualifying.predict",
        "post_qualifying.publish",
        "result.ingest",
        "result.evaluate",
    ],
)
@pytest.mark.parametrize("phase", ["before", "after"])
def test_worker_stage_failure_preserves_last_good_and_recovers(replay, stage, phase):
    replay.drain()
    saved = replay.public()
    if stage.startswith("result."):
        replay.now = time("2026-05-02T15:30:00+00:00")
        replay.drain()
    replay.now = time(
        "2026-05-03T16:00:00+00:00"
        if stage.startswith("result.")
        else "2026-05-02T15:30:00+00:00"
    )
    handlers = replay.handlers()
    original = handlers[stage]

    def interrupted(job):
        if phase == "after":
            original(job)
        raise requests.Timeout("WP14 injected source/worker interruption")

    handlers[stage] = interrupted
    for _ in range(15):
        if not replay.ledger.run_once("fault-worker", handlers):
            break
    with replay.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT status,attempts,last_error FROM orchestration_jobs "
                "WHERE kind=:kind"
            ),
            {"kind": stage},
        ).one()
        assert row.status == "pending" and row.attempts == 1
        assert "interruption" in row.last_error
    assert replay.public() == saved
    after_failure = replay.hashes()
    replay.now += timedelta(seconds=16)
    replay.drain()
    replay.now = time("2026-05-03T16:00:00+00:00")
    replay.drain()
    assert replay.public() == saved
    # A completed-but-unacknowledged handler must retain all committed rows.
    if phase == "after":
        after_retry = replay.hashes()
        for table in ("raw_provider_snapshots", "result_revisions", "evaluation_runs"):
            if after_failure[table]["count"] == after_retry[table]["count"]:
                assert after_failure[table] == after_retry[table]
    with replay.engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM orchestration_jobs WHERE status='succeeded'")
            ).scalar_one()
            == 9
        )


@pytest.mark.parametrize("horizon", ["pre_weekend", "post_qualifying"])
def test_feature_retry_reuses_partially_committed_observation(
    replay, horizon, monkeypatch
):
    if horizon == "post_qualifying":
        replay.drain()
        saved = replay.public()
        replay.now = time("2026-05-02T15:30:00+00:00")
    captured_at = replay.now
    original = replay.store.record_feature_snapshot
    failed = False

    def after_raw_commit(**kwargs):
        nonlocal failed
        if not failed:
            failed = True
            raise requests.Timeout(
                "interrupted after raw commit, before feature commit"
            )
        return original(**kwargs)

    monkeypatch.setattr(replay.store, "record_feature_snapshot", after_raw_commit)
    replay.drain()
    assert failed
    raw_before = replay.hashes()["raw_provider_snapshots"]
    replay.fixture["entries"][0]["standings"] = 22
    replay.fixture["entries"][0]["qualifying"] = 22
    if horizon == "post_qualifying":
        with replay.engine.begin() as conn:
            conn.execute(
                text("UPDATE qualifying_results SET grid_position=22 WHERE driver_id=1")
            )
    replay.now += timedelta(seconds=16)
    replay.drain()
    feature_job = next(
        job for job in weekend_graph(replay.event) if job.kind == f"{horizon}.feature"
    )
    assert replay.ledger.status(feature_job.key) == "succeeded"
    assert replay.hashes()["raw_provider_snapshots"] == raw_before
    assert replay.inputs[horizon].input_cutoff_at == captured_at
    assert replay.inputs[horizon].issue_at == captured_at
    first = replay.frames[horizon].iloc[0]
    assert first.driver_championship_position_race_only == 1
    if horizon == "post_qualifying":
        assert first.qualifying_position == 2
        assert replay.public() == saved
    else:
        assert all(
            p == pytest.approx(1 / 22)
            for p in replay.predictions[horizon]["winner"].values()
        )
    assert replay.public(horizon)["state"] == "published"


def test_evaluation_retry_preserves_first_commit_and_finishes_missing_horizon(
    replay, monkeypatch
):
    replay.drain()
    replay.now = time("2026-05-02T15:30:00+00:00")
    replay.drain()
    saved = replay.public()
    replay.now = time("2026-05-03T16:00:00+00:00")
    original = replay.store.record_evaluation
    failed = False

    def after_first_commit(**kwargs):
        nonlocal failed
        result = original(**kwargs)
        if not failed:
            failed = True
            raise requests.Timeout("interrupted after first evaluation commit")
        return result

    monkeypatch.setattr(replay.store, "record_evaluation", after_first_commit)
    replay.drain()
    with replay.engine.connect() as conn:
        first = dict(
            conn.execute(text("SELECT * FROM evaluation_runs")).mappings().one()
        )
    replay.now += timedelta(seconds=16)
    replay.drain()
    with replay.engine.connect() as conn:
        retained = dict(
            conn.execute(
                text("SELECT * FROM evaluation_runs WHERE evaluation_id=:id"),
                {"id": first["evaluation_id"]},
            )
            .mappings()
            .one()
        )
        assert retained == first
        assert (
            conn.execute(text("SELECT count(*) FROM evaluation_runs")).scalar_one() == 2
        )
    assert replay.public() == saved
    assert (
        replay.ledger.status(
            next(
                j.key
                for j in weekend_graph(replay.event)
                if j.kind == "result.evaluate"
            )
        )
        == "succeeded"
    )


def test_duplicate_workers_claim_once_and_recover_lost_lease(replay):
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(
            pool.map(lambda worker: replay.ledger.claim_due(worker), ["one", "two"])
        )
    job = next(j for j in claimed if j is not None)
    assert sum(j is not None for j in claimed) == 1
    replay.handlers()[job.kind](job)  # durable work committed; acknowledgment lost
    original_raw = replay.hashes()["raw_provider_snapshots"]
    replay.now += timedelta(minutes=31)
    restarted = JobLedger(replay.engine, now=lambda: replay.now)
    assert restarted.recover_expired_leases() == 1
    retried = restarted.claim_due("replacement")
    assert retried.key == job.key
    replay.handlers()[retried.kind](retried)
    restarted.finish(retried, "replacement")
    replay.drain()
    assert replay.hashes()["raw_provider_snapshots"] == original_raw
    saved = replay.public()
    replay.store.publish(replay.runs["pre_weekend"], published_at=replay.now)
    assert replay.public() == saved
    with replay.engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM forecast_publications")
            ).scalar_one()
            == 1
        )


def test_sprint_late_qualifying_weather_withdrawal_reserve_transfer(replay):
    pre = weekend_graph(replay.event)[0]
    assert pre.payload["pre_cutoff"] == "2026-05-01T13:59:00+00:00"
    replay.drain()
    assert replay.inputs["pre_weekend"].input_manifest["weather"] == {
        "availability": "unavailable",
        "rain_probability": None,
    }
    replay.now = time("2026-05-02T14:45:00+00:00")
    replay.drain()
    assert replay.public("post_qualifying")["state"] == "unavailable"
    replay.now = time("2026-05-02T15:30:00+00:00")
    replay.drain()
    prediction = replay.predictions["post_qualifying"]
    assert prediction["order"][0] == "entry:202602"
    assert (
        "entry:202622" in prediction["winner"]
    )  # withdrawal never silently shrinks intended field
    with replay.engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT role FROM event_entries WHERE driver_id=22")
            ).scalar_one()
            == "reserve"
        )
        assert (
            conn.execute(
                text("SELECT constructor_id FROM event_entries WHERE driver_id=21")
            ).scalar_one()
            == 2
        )
    with pytest.raises(JobBlocked, match="incomplete"):
        qualifying_publication_ready(
            ingested_entries=21, expected_entries=22, grid_verified=True
        )
    replay.frames["pre_weekend"]["qualifying_position"] = 1
    with pytest.raises(TemporalViolation):
        validate_features(replay.frames["pre_weekend"], "pre_weekend")


def test_cancellation_supersedes_pending_but_retains_last_good(replay):
    replay.drain()
    saved = replay.public()
    replay.ledger.reconcile(replace(replay.event, lifecycle="cancelled"))
    assert weekend_graph(replace(replay.event, lifecycle="cancelled")) == []
    replay.now = time("2026-05-03T16:00:00+00:00")
    replay.drain()
    assert replay.public() == saved and "post_qualifying" not in replay.runs
    with replay.engine.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM orchestration_jobs WHERE status='superseded'"
                )
            ).scalar_one()
            == 6
        )


def test_season_rollover_preserves_event_context(engine, tmp_path):
    first = WeekendReplay(engine, tmp_path / "first").complete()
    next_season = WeekendReplay(
        engine, tmp_path / "first", season=2027, race_id=2027
    ).complete()
    assert first.public()["run"]["run_id"] != next_season.public()["run"]["run_id"]
    with first.client() as client:
        assert client.get("/api/v1/seasons/2027/events/2026").status_code == 404
        assert {s["year"] for s in client.get("/api/v1/seasons").json()["seasons"]} == {
            2026,
            2027,
        }


@pytest.mark.parametrize(
    "component", ["model", "training_data", "feature_schema", "calibration"]
)
def test_model_bundle_tamper_fails_closed_keeps_saved_reads(replay, component):
    replay.drain()
    saved = replay.public()
    target = replay.root / "artifacts" / replay.bundle[component]["path"]
    target.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        verify_bundle(replay.root / "artifacts", replay.bundle_path, replay.bundle_hash)
    assert replay.public() == saved


def test_model_manifest_tamper_and_db_binding(replay):
    raw = replay.bundle_path.read_bytes()
    replay.bundle_path.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="manifest checksum"):
        replay.load_model()
    replay.bundle_path.write_bytes(raw)
    changed = {
        **replay.bundle,
        "calibration": {**replay.bundle["calibration"], "path": "wrong"},
    }
    with pytest.raises(ValueError, match="persisted lineage"):
        verify_selection(replay.engine, changed)


def test_corrupt_stored_output_hash_is_rejected(replay):
    from gridoracle.ops import recovery

    replay.drain()
    with replay.engine.begin() as conn:
        # Fault injection only in this randomly named disposable database:
        # simulate a corrupted restore that bypassed the immutable SQL trigger.
        conn.execute(text("SET LOCAL session_replication_role = replica"))
        conn.execute(
            text(
                "UPDATE forecast_entry_outputs SET output='{}' WHERE ent"
                "ry_key='entry:202601'"
            )
        )
    with pytest.raises(ValueError, match="stored forecast output checksum"):
        recovery.inventory(replay.engine, replay.root / "artifacts")


def test_new_database_restore_verifies_bundle_and_all_lineage(
    replay, tmp_path, monkeypatch
):
    container = os.environ.get("WP14_POSTGRES_CONTAINER")
    if not container:
        pytest.fail("restore acceptance requires WP14_POSTGRES_CONTAINER")
    replay.complete()
    before = replay.public()
    lineage = replay.hashes()
    backup = tmp_path / "backup"
    backup.mkdir()
    database = replay.engine.url.database
    command = [
        "docker",
        "exec",
        container,
        "pg_dump",
        "-U",
        "postgres",
        "-Fc",
        "--no-owner",
        "--no-acl",
        database,
    ]
    (backup / "database.dump").write_bytes(
        subprocess.run(command, check=True, capture_output=True).stdout
    )
    monkeypatch.setenv("DATABASE_URL", str(replay.engine.url))
    receipt = seal(
        backup, replay.root / "artifacts", replay.bundle_path, replay.bundle_hash
    )
    restored = "wp14_" + uuid.uuid4().hex
    admin = create_engine(
        replay.engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    engine = create_engine(replay.engine.url.set(database=restored))
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {restored}"))
    live = tmp_path / "replacement"
    shutil.copytree(backup / "artifacts", live / "artifacts")
    shutil.copyfile(backup / "bundle.json", live / "bundle.json")
    try:
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                container,
                "pg_restore",
                "-U",
                "postgres",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                "-d",
                restored,
            ],
            input=(backup / "database.dump").read_bytes(),
            capture_output=True,
            check=True,
        )
        compare(
            engine,
            backup,
            receipt,
            live / "artifacts",
            live / "bundle.json",
            replay.bundle_hash,
        )
        assert inventory(engine, live / "artifacts") == lineage
        replay.engine = engine
        replay.store.engine = engine
        assert replay.public() == before
        (live / "artifacts" / replay.bundle["model"]["path"]).write_bytes(b"tamper")
        with pytest.raises(ValueError, match="restored artifact tree"):
            compare(
                engine,
                backup,
                receipt,
                live / "artifacts",
                live / "bundle.json",
                replay.bundle_hash,
            )
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE {restored} WITH (FORCE)"))
        admin.dispose()


def test_sql_trigger_prevents_issued_history_mutation(replay):
    from sqlalchemy.exc import DBAPIError

    replay.drain()
    saved = replay.public()
    with (
        pytest.raises(DBAPIError, match="immutable provenance"),
        replay.engine.begin() as conn,
    ):
        conn.execute(text("UPDATE forecast_entry_outputs SET output='{}'"))
    assert replay.public() == saved


def test_wp04_to_head_upgrade_preserves_issued_forecast(replay):
    from alembic import command

    from scripts.db_migrate import _alembic_config, upgrade_database

    replay.drain()
    saved = replay.public()
    hashes = replay.hashes()
    # Disposable simulation of an installation still at WP03, then WP04 upgrade.
    command.downgrade(_alembic_config(str(replay.engine.url)), "20260929_04")
    assert schema_revision(replay.engine) == "20260929_04"
    upgrade_database(str(replay.engine.url))
    assert schema_revision(replay.engine) == "20260929_05"
    assert replay.public() == saved and replay.hashes() == hashes


@pytest.mark.parametrize("horizon", ["pre_weekend", "post_qualifying"])
def test_retained_trained_model_load_and_hash(horizon, tmp_path):
    from pipeline.benchmark.data import load_dataset
    from pipeline.selection.interface import Classical
    from pipeline.selection.outputs import Field
    from scripts.regression.replay import ROOT

    lock = json.loads((ROOT / "docs/models/wp09/input-lock.json").read_text())
    suffix = f"/models/{horizon}__xgb_regression__full__2023.json.gz"
    name, checksum = next(
        (n, h) for n, h in lock["files"].items() if n.endswith(suffix)
    )
    model = Classical(ROOT / name, checksum, horizon)
    frames, _, _ = load_dataset(tmp_path / "dataset")
    frame = frames[horizon]
    frame = frame[frame.race_key == "2023:1"]
    field = Field(
        "2023:1",
        horizon,
        frame.cutoff.iloc[0],
        "retained-wp05",
        tuple(frame.driver_identity_key),
        provenance="exploratory",
        teams=tuple(
            zip(frame.driver_identity_key, frame.constructor_identity_key, strict=True)
        ),
    )
    prediction = model.predict(frame, field)
    field.check(prediction)
    with pytest.raises(ValueError, match="checksum"):
        Classical(ROOT / name, "0" * 64, horizon)
