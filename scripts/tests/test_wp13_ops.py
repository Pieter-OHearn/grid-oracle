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
