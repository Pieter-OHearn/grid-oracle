"""Recovery corruption must fail before migration or public readiness."""

import json
from hashlib import sha256

import pytest

from api.tests.public_fixture import build_fixture
from gridoracle.ops.bundle import verify_bundle
from gridoracle.ops.recovery import file_hash, inventory, verify_recovery_set
from gridoracle.provenance import ContentAddressedArtifactStore


def bundle_fixture(tmp_path):
    root = tmp_path / "artifacts"
    store = ContentAddressedArtifactStore(root)
    refs = {}
    for name, namespace in [
        ("model", "models/fixture"),
        ("training_data", "datasets/fixture"),
        ("feature_schema", "schemas/fixture"),
        ("calibration", "calibrators/fixture"),
    ]:
        ref = store.put_bytes(namespace, name.encode())
        refs[name] = {"id": "fixture", "path": ref.path, "sha256": ref.sha256}
    value = {
        "format": "gridoracle-model-bundle-v1",
        **refs,
        "artifacts": list(refs.values()),
        "code_revision": "fixture",
        "runtime_image": "fixture",
        "model_manifest_id": "model",
        "dataset_id": "dataset",
        "feature_snapshot_id": "features",
        "calibrator_manifest_id": "calibrator",
    }
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(value))
    return root, path, file_hash(path)


def test_offline_bundle_detects_changed_manifest_and_dependency(tmp_path):
    root, path, expected = bundle_fixture(tmp_path)
    value = verify_bundle(root, path, expected)
    (root / value["model"]["path"]).write_text("corrupt")
    with pytest.raises(ValueError, match="checksum"):
        verify_bundle(root, path, expected)
    path.write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        verify_bundle(root, path, expected)


def test_bundle_rejects_missing_training_data_and_wrong_model_identity(tmp_path):
    root, path, _ = bundle_fixture(tmp_path)
    value = json.loads(path.read_text())
    value["model"]["id"] = "other"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="identity"):
        verify_bundle(root, path, file_hash(path))
    value["model"]["id"] = "fixture"
    (root / value["training_data"]["path"]).unlink()
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="missing"):
        verify_bundle(root, path, file_hash(path))


def test_lineage_inventory_verifies_every_persisted_forecast_hash(tmp_path):
    engine, _, _ = build_fixture(
        f"sqlite:///{tmp_path / 'db.sqlite'}", tmp_path / "artifacts"
    )
    try:
        evidence = inventory(engine, tmp_path / "artifacts")
        assert evidence["forecast_entry_outputs"]["count"] == 88
        assert evidence["forecast_publications"]["count"] == 2
        assert evidence == inventory(engine, tmp_path / "artifacts")
        ref = next((tmp_path / "artifacts" / "models").rglob("sha256/*"))
        ref.write_text("corrupt")
        with pytest.raises(ValueError, match="checksum"):
            inventory(engine, tmp_path / "artifacts")
    finally:
        engine.dispose()


def test_recovery_set_is_externally_pinned_and_rejects_extra_or_changed_files(tmp_path):
    _, _, _ = bundle_fixture(tmp_path)
    (tmp_path / "database.dump").write_bytes(b"fixture-only-not-a-postgres-archive")
    files = {
        p.relative_to(tmp_path).as_posix(): file_hash(p)
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    receipt = tmp_path / "recovery.json"
    receipt.write_text(json.dumps({"format": "gridoracle-recovery-v1", "files": files}))
    expected = sha256(receipt.read_bytes()).hexdigest()
    verify_recovery_set(tmp_path, expected)
    (tmp_path / "injected").write_text("unexpected")
    with pytest.raises(ValueError, match="unrecorded"):
        verify_recovery_set(tmp_path, expected)
    (tmp_path / "injected").unlink()
    receipt.write_text("{}")
    with pytest.raises(ValueError, match="receipt"):
        verify_recovery_set(tmp_path, expected)


def test_selected_bundle_must_match_database_model_and_calibrator(tmp_path):
    from sqlalchemy import text

    from gridoracle.ops.bundle import verify_selection

    engine, _, _ = build_fixture(
        f"sqlite:///{tmp_path / 'db.sqlite'}", tmp_path / "artifacts"
    )
    try:
        value = {
            "model_manifest_id": "model",
            "dataset_id": "dataset",
            "feature_snapshot_id": "features",
            "calibrator_manifest_id": "calibrator",
        }
        with engine.connect() as conn:
            for table, component in [
                ("model_manifests", "model"),
                ("dataset_manifests", "training_data"),
                ("calibrator_manifests", "calibration"),
            ]:
                row = conn.execute(text(f"SELECT * FROM {table}")).mappings().one()
                value[component] = {
                    "id": "fixture",
                    "path": row["artifact_path"],
                    "sha256": row["sha256"],
                }
        verify_selection(engine, value)
        value["calibration"]["sha256"] = "f" * 64
        with pytest.raises(ValueError, match="persisted lineage"):
            verify_selection(engine, value)
    finally:
        engine.dispose()


def test_stored_unicode_output_hash_matches_integrated_provenance_contract():
    from gridoracle.ops.bundle import digest
    from gridoracle.provenance.store import _digest

    assert digest({"name": "Équipe", "win_probability": 0.25}) == _digest(
        {"name": "Équipe", "win_probability": 0.25}
    )


def sealed_fixture(tmp_path, monkeypatch, *, empty=False):
    import shutil

    from sqlalchemy import create_engine, event, text

    from scripts import wp13_recovery

    source = tmp_path / "source"
    source.mkdir()
    if empty:
        engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
        root, bundle, expected = bundle_fixture(source)
    else:
        root = source / "artifacts"
        engine, _, _ = build_fixture(f"sqlite:///{tmp_path / 'db.sqlite'}", root)
        _, template, _ = bundle_fixture(tmp_path / "template")
        value = json.loads(template.read_text())
        with engine.connect() as conn:
            for table, component in [
                ("model_manifests", "model"),
                ("dataset_manifests", "training_data"),
                ("calibrator_manifests", "calibration"),
            ]:
                row = conn.execute(text(f"SELECT * FROM {table}")).mappings().one()
                value[component] = {
                    "id": "fixture",
                    "path": row["artifact_path"],
                    "sha256": row["sha256"],
                }
        ref = ContentAddressedArtifactStore(root).put_bytes(
            "schemas/fixture", b"schema"
        )
        value["feature_schema"] = {
            "id": "fixture",
            "path": ref.path,
            "sha256": ref.sha256,
        }
        value["artifacts"] = [
            value[name]
            for name in ("model", "training_data", "feature_schema", "calibration")
        ]
        bundle = source / "bundle.json"
        bundle.write_text(json.dumps(value))
        expected = file_hash(bundle)
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.create_function(
            "current_database", 0, lambda: "fixture"
        ),
    )
    engine.dispose()
    monkeypatch.setattr(wp13_recovery, "create_engine", lambda _: engine)
    monkeypatch.setenv("DATABASE_URL", str(engine.url))
    monkeypatch.setenv("GRIDORACLE_ARTIFACT_ROOT", str(root))
    monkeypatch.setenv("GRIDORACLE_BUNDLE_FILE", str(bundle))
    monkeypatch.setenv("GRIDORACLE_BUNDLE_SHA256", expected)
    backup = tmp_path / "backup"
    backup.mkdir()
    (backup / "database.dump").write_bytes(b"unit fixture archive")
    receipt = wp13_recovery.seal(backup, root, bundle, expected)
    runtime = tmp_path / "replacement"
    shutil.copytree(source, runtime)
    return (
        engine,
        backup,
        receipt,
        runtime / "artifacts",
        runtime / "bundle.json",
        expected,
    )


def test_compare_verifies_actual_replacement_mounts(tmp_path, monkeypatch):
    from scripts.wp13_recovery import compare

    engine, backup, receipt, root, bundle, expected = sealed_fixture(
        tmp_path, monkeypatch
    )
    compare(engine, backup, receipt, root, bundle, expected)
    # The sealed copy stays healthy while the separate live raw snapshot is corrupt.
    from sqlalchemy import text

    with engine.connect() as conn:
        ref = (
            root
            / conn.execute(
                text("SELECT artifact_path FROM raw_provider_snapshots LIMIT 1")
            ).scalar_one()
        )
    original = ref.read_bytes()
    ref.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="artifact tree differs"):
        compare(engine, backup, receipt, root, bundle, expected)
    ref.write_bytes(original)
    with pytest.raises(ValueError, match="directory is missing"):
        compare(engine, backup, receipt, root / "missing", bundle, expected)
    with pytest.raises(ValueError, match="runtime bundle differs"):
        compare(engine, backup, receipt, root, bundle, "f" * 64)
    bundle.write_text("{}")
    with pytest.raises(ValueError, match="manifest checksum"):
        compare(engine, backup, receipt, root, bundle, expected)
    engine.dispose()


def test_empty_and_pre_ledger_restore_comparison(tmp_path, monkeypatch):
    from sqlalchemy import text

    from scripts.wp13_recovery import compare

    engine, backup, receipt, root, bundle, expected = sealed_fixture(
        tmp_path, monkeypatch, empty=True
    )
    compare(engine, backup, receipt, root, bundle, expected)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE legacy_core (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE result_revisions (id INTEGER PRIMARY KEY)"))
    compare(engine, backup, receipt, root, bundle, expected)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num TEXT)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('unexpected')"))
    with pytest.raises(ValueError, match="schema revision differs"):
        compare(engine, backup, receipt, root, bundle, expected)
    engine.dispose()


def test_missing_migration_ledger_and_changed_runtime_fail_before_upgrade(
    tmp_path, monkeypatch
):
    from unittest.mock import Mock

    from sqlalchemy import text

    from scripts import wp13_migrate

    engine, backup, receipt, _, _, _ = sealed_fixture(tmp_path, monkeypatch)
    upgrade = Mock()
    monkeypatch.setattr(wp13_migrate, "create_engine", lambda _: engine)
    monkeypatch.setattr(wp13_migrate, "upgrade_database", upgrade)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE alembic_version RENAME TO saved_revision"))
    with pytest.raises(ValueError, match="schema changed since backup"):
        wp13_migrate.migrate(backup, receipt)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE saved_revision RENAME TO alembic_version"))
    from pathlib import Path

    root = Path(__import__("os").environ["GRIDORACLE_ARTIFACT_ROOT"])
    (root / "unexpected").write_text("extra")
    with pytest.raises(ValueError, match="artifact tree differs"):
        wp13_migrate.migrate(backup, receipt)
    upgrade.assert_not_called()
    engine.dispose()


def test_v1_receipts_remain_readable(tmp_path, monkeypatch):
    from scripts.wp13_recovery import compare

    engine, backup, _, root, bundle, expected = sealed_fixture(tmp_path, monkeypatch)
    path = backup / "recovery.json"
    receipt = json.loads(path.read_text())
    receipt["format"] = "gridoracle-recovery-v1"
    receipt["lineage"] = inventory(engine, root, legacy=True)
    path.write_text(json.dumps(receipt))
    compare(engine, backup, file_hash(path), root, bundle, expected)
    engine.dispose()


def test_large_lineage_inventory_has_bounded_memory(monkeypatch, tmp_path):
    import tracemalloc
    from contextlib import nullcontext

    from gridoracle.ops import recovery

    class Connection:
        def execution_options(self, **options):
            assert options == {"yield_per": 100}
            return self

        def execute(self, query):
            assert str(query).endswith("ORDER BY evaluation_id")
            return self

        def mappings(self):
            return (
                {"evaluation_id": str(i), "metrics": "x" * 4000} for i in range(6000)
            )

    class Engine:
        def connect(self):
            return nullcontext(Connection())

    monkeypatch.setattr(recovery, "LINEAGE_TABLES", ("evaluation_runs",))
    tracemalloc.start()
    try:
        result = inventory(Engine(), tmp_path)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert result["evaluation_runs"]["count"] == 6000
    assert peak < 8 * 1024 * 1024


def test_worker_blocks_legacy_evaluation_selector(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from gridoracle.ops.runtime import worker_tick
    from pipeline import orchestration, scheduler

    ledger = Mock()
    job = SimpleNamespace(kind=orchestration.EVALUATE)
    ledger.claim_due.return_value = job
    monkeypatch.setattr(orchestration, "JobLedger", lambda _: ledger)
    handler = Mock()
    monkeypatch.setattr(scheduler, "_run_durable_job", handler)
    assert worker_tick(object())
    handler.assert_not_called()
    assert isinstance(ledger.finish.call_args.args[2], orchestration.JobBlocked)
    assert "bundle-aware evaluation" in str(ledger.finish.call_args.args[2])
