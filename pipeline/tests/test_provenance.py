"""WP03 acceptance tests for immutable forecast lineage and publication."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from gridoracle.provenance.artifacts import (
    ArtifactIntegrityError,
    ContentAddressedArtifactStore,
)
from gridoracle.provenance.store import (
    ForecastEntry,
    ForecastRunInput,
    IdempotencyConflict,
    ImmutableProvenanceStore,
    ProvenanceError,
)
from scripts.db_migrate import LEGACY_CORE_TABLES, upgrade_database
from sqlalchemy import create_engine, text

NOW = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
RACE_START = NOW + timedelta(days=3)


@pytest.fixture
def provenance(tmp_path):
    """A migrated known-legacy fixture, never a live or reset database."""
    database_url = f"sqlite:///{tmp_path / 'wp03.sqlite'}"
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            for table in sorted(LEGACY_CORE_TABLES):
                connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
            for column in (
                "race_id INTEGER",
                "model_version_id INTEGER",
                "driver_id INTEGER",
                "constructor_id INTEGER",
                "predicted_position INTEGER",
                "confidence_score REAL",
                "created_at TEXT",
            ):
                connection.execute(text(f"ALTER TABLE predictions ADD COLUMN {column}"))
            connection.execute(text("INSERT INTO races (id) VALUES (7)"))
            connection.execute(text("INSERT INTO model_versions (id) VALUES (3)"))
    finally:
        engine.dispose()
    upgrade_database(database_url)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO result_revisions
                    (race_id, revision, source, reason, is_official, recorded_at)
                    VALUES (7, 1, 'fixture', 'first official result', 1, :recorded_at),
                           (7, 2, 'fixture', 'corrected official result', 1, :recorded_at)
                    """
                ),
                {"recorded_at": NOW.isoformat()},
            )
        artifacts = ContentAddressedArtifactStore(tmp_path / "artifacts")
        store = ImmutableProvenanceStore(engine, artifacts)
        model = artifacts.put_bytes("models/champion-v1", b"stable-model")
        dataset = artifacts.put_bytes("datasets/2026-round-07", b"dataset")
        features = artifacts.put_bytes("features/2026-round-07", b"features")
        raw = artifacts.put_bytes("providers/jolpica", b"raw-response")
        calibrator = artifacts.put_bytes("calibrators/champion-v1", b"calibrator")
        store.record_raw_snapshot(
            snapshot_id="raw-1",
            provider="jolpica",
            retrieved_at=NOW,
            source_available_at=NOW - timedelta(minutes=5),
            artifact_path=raw.path,
            sha256=raw.sha256,
            manifest={"url": "https://example.test/results"},
        )
        store.record_dataset(
            dataset_id="dataset-1",
            artifact_path=dataset.path,
            sha256=dataset.sha256,
            manifest={"schema": "dataset/v1"},
        )
        store.record_feature_snapshot(
            feature_snapshot_id="feature-1",
            dataset_id="dataset-1",
            artifact_path=features.path,
            sha256=features.sha256,
            manifest={"cutoff": NOW.isoformat()},
        )
        store.record_model_manifest(
            model_manifest_id="model-1",
            model_id="champion-v1",
            model_version_id=3,
            artifact_path=model.path,
            sha256=model.sha256,
            manifest={"format": "xgboost-json", "seed": 7},
        )
        store.record_calibrator_manifest(
            calibrator_manifest_id="calibrator-1",
            model_manifest_id="model-1",
            artifact_path=calibrator.path,
            sha256=calibrator.sha256,
            manifest={"method": "isotonic"},
        )
        yield store, engine, artifacts
    finally:
        engine.dispose()


def _run(*, key: str, horizon: str = "pre_weekend", issue_at: datetime = NOW):
    return ForecastRunInput(
        race_id=7,
        horizon=horizon,
        input_cutoff_at=issue_at - timedelta(minutes=10),
        issue_at=issue_at,
        source_available_at=issue_at - timedelta(minutes=15),
        provenance_grade="verified",
        expected_entry_count=2,
        idempotency_key=key,
        input_manifest={
            "contract_version": "2026.1",
            "expected_outputs": {
                "entry:driver-1": {"win_probability": 0.6000000000001, "rank": 1},
                "entry:driver-2": {"win_probability": 0.3999999999999, "rank": 2},
            },
        },
        raw_snapshot_id="raw-1",
        dataset_id="dataset-1",
        feature_snapshot_id="feature-1",
        model_manifest_id="model-1",
        calibrator_manifest_id="calibrator-1",
        reproduction_tolerance=1e-12,
    )


def _entries():
    return [
        ForecastEntry("entry:driver-1", {"win_probability": 0.6000000000001, "rank": 1}),
        ForecastEntry("entry:driver-2", {"win_probability": 0.3999999999999, "rank": 2}),
    ]


def test_two_horizons_coexist_and_identical_retry_preserves_history(provenance):
    store, engine, _artifacts = provenance
    pre = _run(key="pre-race-7", horizon="pre_weekend")
    pre_id = store.create_forecast_run(pre)
    assert store.create_forecast_run(pre) == pre_id
    store.add_entry_outputs(pre_id, _entries())
    store.add_entry_outputs(pre_id, _entries())
    assert store.publish(pre_id, race_start_at=RACE_START, published_at=NOW) == pre_id

    post = _run(
        key="post-qualifying-7",
        horizon="post_qualifying",
        issue_at=NOW + timedelta(days=1),
    )
    post_id = store.create_forecast_run(post)
    store.add_entry_outputs(post_id, _entries())
    store.publish(post_id, race_start_at=RACE_START, published_at=NOW + timedelta(days=1))

    with engine.connect() as connection:
        publications = connection.execute(
            text("SELECT horizon, forecast_run_id FROM forecast_publications ORDER BY horizon")
        ).fetchall()
        outputs = connection.execute(
            text("SELECT count(*) FROM forecast_entry_outputs WHERE forecast_run_id = :run_id"),
            {"run_id": pre_id},
        ).scalar_one()
    assert publications == [("post_qualifying", post_id), ("pre_weekend", pre_id)]
    assert outputs == 2

    with pytest.raises(IdempotencyConflict, match="different immutable output"):
        store.add_entry_outputs(
            pre_id,
            [ForecastEntry("entry:driver-1", {"win_probability": 0.1, "rank": 1})],
        )


def test_incomplete_field_and_post_race_run_cannot_publish(provenance):
    store, _engine, _artifacts = provenance
    incomplete_id = store.create_forecast_run(_run(key="partial-field"))
    store.add_entry_outputs(incomplete_id, _entries()[:1])
    with pytest.raises(ProvenanceError, match="incomplete field"):
        store.publish(incomplete_id, race_start_at=RACE_START, published_at=NOW)

    post_race = _run(key="after-race", issue_at=RACE_START + timedelta(minutes=1))
    post_race_id = store.create_forecast_run(post_race)
    store.add_entry_outputs(post_race_id, _entries())
    with pytest.raises(ProvenanceError, match="post-race output"):
        store.publish(
            post_race_id,
            race_start_at=RACE_START,
            published_at=RACE_START + timedelta(minutes=2),
        )


def test_invalid_hash_and_model_path_mismatch_fail(provenance):
    store, _engine, artifacts = provenance
    bad = artifacts.put_bytes("datasets/bad-hash", b"bytes")
    with pytest.raises(ProvenanceError, match="checksum failure"):
        store.record_dataset(
            dataset_id="bad-dataset",
            artifact_path=bad.path,
            sha256="0" * 64,
            manifest={},
        )
    with pytest.raises(ArtifactIntegrityError, match="declared SHA-256"):
        artifacts.put_bytes("datasets/declared-bad", b"bytes", declared_sha256="f" * 64)

    other_model = artifacts.put_bytes("models/not-champion", b"different-model")
    with pytest.raises(ProvenanceError, match="model ID/artifact path mismatch"):
        store.record_model_manifest(
            model_manifest_id="wrong-path",
            model_id="champion-v1",
            artifact_path=other_model.path,
            sha256=other_model.sha256,
            manifest={},
        )


def test_evaluation_revisions_and_fresh_reproduction_do_not_change_forecast(provenance):
    store, engine, artifacts = provenance
    run_id = store.create_forecast_run(_run(key="evaluation-target"))
    store.add_entry_outputs(run_id, _entries())
    store.publish(run_id, race_start_at=RACE_START, published_at=NOW)
    with engine.connect() as connection:
        before = connection.execute(
            text("SELECT output_sha256 FROM forecast_entry_outputs WHERE forecast_run_id = :run_id ORDER BY entry_key"),
            {"run_id": run_id},
        ).fetchall()

    store.record_evaluation(
        evaluation_id="evaluation-v1",
        forecast_run_id=run_id,
        result_revision_id=1,
        evaluator_manifest={"metric": "winner_log_loss", "revision": 1},
        metrics={"winner_log_loss": 0.5},
        evaluated_at=RACE_START + timedelta(hours=2),
    )
    store.record_evaluation(
        evaluation_id="evaluation-v2",
        forecast_run_id=run_id,
        result_revision_id=2,
        evaluator_manifest={"metric": "winner_log_loss", "revision": 2},
        metrics={"winner_log_loss": 0.4},
        evaluated_at=RACE_START + timedelta(hours=3),
    )
    fresh_process = ImmutableProvenanceStore(engine, artifacts)
    fresh_process.verify_reproduction(run_id, lambda manifest: manifest["expected_outputs"])

    with engine.connect() as connection:
        after = connection.execute(
            text("SELECT output_sha256 FROM forecast_entry_outputs WHERE forecast_run_id = :run_id ORDER BY entry_key"),
            {"run_id": run_id},
        ).fetchall()
        evaluation_count = connection.execute(
            text("SELECT count(*) FROM evaluation_runs WHERE forecast_run_id = :run_id"),
            {"run_id": run_id},
        ).scalar_one()
    assert after == before
    assert evaluation_count == 2

    with pytest.raises(Exception, match="immutable provenance"):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE forecast_entry_outputs SET output_sha256 = 'tampered' WHERE forecast_run_id = :run_id"),
                {"run_id": run_id},
            )


def test_legacy_import_preserves_known_values_without_inventing_lineage(provenance):
    store, engine, _artifacts = provenance
    legacy_time = datetime(2024, 11, 3, 8, 30, tzinfo=timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO predictions
                (id, race_id, model_version_id, driver_id, constructor_id,
                 predicted_position, confidence_score, created_at)
                VALUES
                (41, 7, 3, 101, 201, 1, 0.8, :created_at),
                (42, 7, 3, 102, 201, 2, 0.2, :created_at)
                """
            ),
            {"created_at": legacy_time.isoformat()},
        )
    imported = store.import_legacy_predictions()
    assert len(imported) == 1
    assert store.import_legacy_predictions() == imported
    run_id = imported[0]
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT provenance_grade, issue_at, input_manifest FROM forecast_runs WHERE forecast_run_id = :run_id"
            ),
            {"run_id": run_id},
        ).one()
    assert row.provenance_grade == "legacy_unverified"
    assert legacy_time.isoformat() in str(row.issue_at)
    assert "unknown_fields" in row.input_manifest
    with engine.connect() as connection:
        preserved = connection.execute(
            text(
                """
                SELECT output FROM forecast_entry_outputs
                WHERE forecast_run_id = :run_id ORDER BY entry_key
                """
            ),
            {"run_id": run_id},
        ).fetchall()
    assert "legacy_prediction_id" in str(preserved)
    assert "0.8" in str(preserved)
    with pytest.raises(ProvenanceError, match="legacy_unverified"):
        store.publish(run_id, race_start_at=RACE_START, published_at=NOW)
