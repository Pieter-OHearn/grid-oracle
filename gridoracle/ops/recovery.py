"""Inventory the immutable lineage and verify a sealed recovery directory."""

import json
from hashlib import sha256
from pathlib import Path

from sqlalchemy import inspect, text

from gridoracle.ops.bundle import canonical, digest, verify_bundle, verify_reference

RECOVERY_FORMAT = "gridoracle-recovery-v2"
LEGACY_FORMAT = "gridoracle-recovery-v1"

MANIFEST_TABLES = (
    "raw_provider_snapshots",
    "dataset_manifests",
    "feature_snapshots",
    "model_manifests",
    "calibrator_manifests",
)
LINEAGE_TABLES = (
    *MANIFEST_TABLES,
    "forecast_runs",
    "forecast_entry_outputs",
    "forecast_publications",
    "result_revisions",
    "evaluation_runs",
)
ORDER_COLUMNS = {
    "raw_provider_snapshots": "snapshot_id",
    "dataset_manifests": "dataset_id",
    "feature_snapshots": "feature_snapshot_id",
    "model_manifests": "model_manifest_id",
    "calibrator_manifests": "calibrator_manifest_id",
    "forecast_runs": "forecast_run_id",
    "forecast_entry_outputs": "forecast_run_id, entry_key",
    "forecast_publications": "race_id, horizon",
    "result_revisions": "id",
    "evaluation_runs": "evaluation_id",
}


def inventory(engine, root: Path, *, legacy: bool = False) -> dict:
    """Fingerprint all immutable rows and verify stored output/artifact hashes."""
    result = {}
    with engine.connect() as conn:
        for table in LINEAGE_TABLES:
            # v2 streams primary-key ordered rows, including a server-side
            # cursor on PostgreSQL. Memory scales with a batch, not the table.
            query = text(f"SELECT * FROM {table} ORDER BY {ORDER_COLUMNS[table]}")
            rows = conn.execution_options(yield_per=100).execute(query).mappings()
            checksum = sha256(b"[")
            count = 0
            old_rows = [] if legacy else None
            for mapping in rows:
                row = dict(mapping)
                if table in MANIFEST_TABLES:
                    verify_reference(
                        root, {"path": row["artifact_path"], "sha256": row["sha256"]}
                    )
                if table == "forecast_entry_outputs":
                    output = row["output"]
                    output = json.loads(output) if isinstance(output, str) else output
                    if digest(output) != row["output_sha256"]:
                        raise ValueError("stored forecast output checksum mismatch")
                # Preserve driver-decoded datetime/Decimal/JSON semantics.
                normal = json.loads(json.dumps(row, sort_keys=True, default=str))
                if legacy:
                    old_rows.append(normal)
                else:
                    if count:
                        checksum.update(b",")
                    checksum.update(canonical(normal))
                count += 1
            checksum.update(b"]")
            result[table] = {
                "count": count,
                "sha256": digest(sorted(old_rows, key=digest))
                if legacy
                else checksum.hexdigest(),
            }
    return result


def schema_revision(engine) -> str | None:
    if "alembic_version" not in inspect(engine).get_table_names():
        return None
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()


def lineage_inventory(engine, root: Path, receipt_format=RECOVERY_FORMAT):
    tables = set(inspect(engine).get_table_names())
    # result_revisions precedes WP03. Other partial provenance structures are
    # not a valid pre-ledger restore; inventory will fail on the missing tables.
    if not tables.intersection(set(LINEAGE_TABLES) - {"result_revisions"}):
        return None
    return inventory(engine, root, legacy=receipt_format == LEGACY_FORMAT)


def file_hash(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_recovery_set(directory: Path, expected_sha256: str) -> dict:
    """External receipt digest pins dump, artifact tree and selected bundle."""
    manifest = directory / "recovery.json"
    if file_hash(manifest) != expected_sha256:
        raise ValueError("recovery receipt checksum mismatch")
    receipt = json.loads(manifest.read_text())
    if receipt.get("format") not in (RECOVERY_FORMAT, LEGACY_FORMAT):
        raise ValueError("unsupported recovery format")
    declared = receipt["files"]
    actual = {}
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("recovery sets must not contain symlinks")
        if path.is_file() and path != manifest:
            actual[path.relative_to(directory).as_posix()] = file_hash(path)
    if actual != declared or "database.dump" not in actual:
        raise ValueError("recovery files missing, changed or unrecorded")
    verify_bundle(
        directory / "artifacts", directory / "bundle.json", actual["bundle.json"]
    )
    return receipt


def verify_runtime_copy(receipt: dict, artifacts: Path, bundle: Path, bundle_hash: str):
    """Check the replacement's actual mounts against the externally pinned set."""
    expected = {
        name.removeprefix("artifacts/"): checksum
        for name, checksum in receipt["files"].items()
        if name.startswith("artifacts/")
    }
    actual = {}
    if not artifacts.is_dir():
        raise ValueError("restored artifact directory is missing")
    for path in artifacts.rglob("*"):
        if path.is_symlink():
            raise ValueError("restored artifacts must not contain symlinks")
        if path.is_file():
            actual[path.relative_to(artifacts).as_posix()] = file_hash(path)
    if actual != expected:
        raise ValueError("restored artifact tree differs from backup")
    if bundle_hash != receipt["files"]["bundle.json"]:
        raise ValueError("selected runtime bundle differs from backup")
    return verify_bundle(artifacts, bundle, bundle_hash)
