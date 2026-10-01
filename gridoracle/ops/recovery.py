"""Inventory the immutable lineage and verify a sealed recovery directory."""

import json
from hashlib import sha256
from pathlib import Path

from sqlalchemy import text

from gridoracle.ops.bundle import digest, verify_bundle, verify_reference

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


def inventory(engine, root: Path) -> dict:
    """Fingerprint all immutable rows and verify stored output/artifact hashes."""
    result = {}
    with engine.connect() as conn:
        for table in LINEAGE_TABLES:
            rows = [
                dict(row)
                for row in conn.execute(text(f"SELECT * FROM {table}")).mappings()
            ]
            for row in rows:
                if table in MANIFEST_TABLES:
                    verify_reference(
                        root, {"path": row["artifact_path"], "sha256": row["sha256"]}
                    )
                if table == "forecast_entry_outputs":
                    output = row["output"]
                    output = json.loads(output) if isinstance(output, str) else output
                    if digest(output) != row["output_sha256"]:
                        raise ValueError("stored forecast output checksum mismatch")
            # Driver-decoded datetime/Decimal/JSON must have identical PostgreSQL
            # semantics before/after restore. This inventory is dialect-specific.
            normal = json.loads(json.dumps(rows, sort_keys=True, default=str))
            result[table] = {
                "count": len(rows),
                "sha256": digest(sorted(normal, key=digest)),
            }
    return result


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
    if receipt.get("format") != "gridoracle-recovery-v1":
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
