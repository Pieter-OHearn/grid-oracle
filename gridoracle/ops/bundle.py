"""Portable, hash-pinned bundle verification without training code or hardware."""

import json
import re
from hashlib import sha256
from pathlib import Path, PurePosixPath

from gridoracle.provenance.artifacts import ContentAddressedArtifactStore


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def digest(value) -> str:
    return sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_reference(root: Path, ref: dict) -> None:
    logical = PurePosixPath(ref["path"])
    checksum = ref["sha256"]
    if (
        not re.fullmatch(r"[0-9a-f]{64}", checksum)
        or logical.is_absolute()
        or ".." in logical.parts
        or logical.parts[-2:] != ("sha256", checksum)
    ):
        raise ValueError("artifact checksum path is invalid")
    target = root / logical
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("artifact path leaves bundle root")
    if not target.is_file():
        raise ValueError("artifact is missing")
    if file_digest(target) != checksum:
        raise ValueError("artifact checksum mismatch")


def verify_bundle(root: Path, manifest: Path, expected_sha256: str) -> dict:
    """Verify the manifest itself and every required offline dependency."""
    raw = manifest.read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("model bundle manifest checksum mismatch")
    bundle = json.loads(raw)
    if bundle.get("format") != "gridoracle-model-bundle-v1":
        raise ValueError("unsupported model bundle format")
    store = ContentAddressedArtifactStore(root)
    for name in ("model", "training_data", "feature_schema", "calibration"):
        ref = bundle[name]
        if not isinstance(ref.get("id"), str) or not ref["id"]:
            raise ValueError(f"missing {name} identity")
        verify_reference(root, ref)
    model = bundle["model"]
    if model["path"] != store.model_path(model["id"], model["sha256"]):
        raise ValueError("bundle model identity/path mismatch")
    if not bundle.get("artifacts"):
        raise ValueError("bundle must enumerate runtime artifacts")
    for ref in bundle["artifacts"]:
        verify_reference(root, ref)
    for name in (
        "code_revision",
        "runtime_image",
        "model_manifest_id",
        "dataset_id",
        "feature_snapshot_id",
        "calibrator_manifest_id",
    ):
        if not isinstance(bundle.get(name), str) or not bundle[name]:
            raise ValueError(f"missing {name}")
    return bundle


def verify_selection(engine, bundle: dict) -> None:
    """Bind the selected offline bundle to the integrated WP03 manifests."""
    from sqlalchemy import text

    checks = (
        ("model_manifests", "model_manifest_id", "model"),
        ("dataset_manifests", "dataset_id", "training_data"),
        ("calibrator_manifests", "calibrator_manifest_id", "calibration"),
    )
    with engine.connect() as conn:
        for table, key, component in checks:
            row = (
                conn.execute(
                    text(f"SELECT * FROM {table} WHERE {key}=:identity"),
                    {"identity": bundle[key]},
                )
                .mappings()
                .one()
            )
            ref = bundle[component]
            if row["artifact_path"] != ref["path"] or row["sha256"] != ref["sha256"]:
                raise ValueError("selected bundle differs from persisted lineage")
            if component == "model" and row["model_id"] != ref["id"]:
                raise ValueError(
                    "selected model identity differs from persisted lineage"
                )
            if (
                component == "calibration"
                and row["model_manifest_id"] != bundle["model_manifest_id"]
            ):
                raise ValueError("calibration belongs to a different model")
        dataset_id = conn.execute(
            text(
                "SELECT dataset_id FROM feature_snapshots WHERE feature_snapshot_id=:id"
            ),
            {"id": bundle["feature_snapshot_id"]},
        ).scalar_one()
        if dataset_id != bundle["dataset_id"]:
            raise ValueError("feature snapshot belongs to a different training dataset")
