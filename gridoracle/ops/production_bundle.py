"""The production bundle for the WP09-retained fixed baselines.

`write` puts the bundle's closure into the artifact store and writes the
bundle JSON, named by its SHA-256, into the bundles directory. It needs no
database, so a fresh installation can seal its first (empty) recovery set
before the schema exists. `register` then records the bundle's manifests in
the migrated database, which serving readiness requires. Both are idempotent:
the same release inputs produce the same bytes and the same rows.
"""

import argparse
import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import create_engine, text

from gridoracle.ops.bundle import canonical, verify_bundle, verify_selection
from gridoracle.ops.runtime import configure
from gridoracle.provenance import (
    ContentAddressedArtifactStore,
    ImmutableProvenanceStore,
)

MODEL_ID = "wp09-fixed-baseline"
DATASET_ID = "wp09-fixed-baseline/v1"
FEATURE_SNAPSHOT_ID = "wp09-fixed-baseline/v1/schema"
MODEL_VERSION_NAME = "WP09 fixed baselines"

MODEL = {
    "format": "gridoracle-fixed-baseline-v1",
    "horizons": {"pre_weekend": "standings", "post_qualifying": "qualifying"},
    "temperature": 4.0,
    "protocol": "wp06-v2",
    "selection": "docs/models/wp09/REPORT.md: fixed fallbacks, no challenger promoted",
}
TRAINING_DATA = {
    "fit": "none; fixed WP09-retained baselines",
    "inputs": "live Jolpica observations frozen per forecast run",
}
FEATURE_SCHEMA = {
    "features": [
        "driver_championship_position_race_only",
        "qualifying_position",
        "missing__qualifying",
    ],
    "dictionary": "docs/datasets/WP05_FEATURE_DICTIONARY.md",
}
CALIBRATION = {"method": "identity", "protocol": "wp06-v2"}


def closure(store, runtime_image, code_revision):
    refs = {}
    for name, namespace, value in (
        ("model", f"models/{MODEL_ID}", MODEL),
        ("training_data", "datasets/wp09-fixed-baseline", TRAINING_DATA),
        ("feature_schema", "schemas/wp09-fixed-baseline", FEATURE_SCHEMA),
        ("calibration", "calibrators/wp09-identity", CALIBRATION),
    ):
        ref = store.put_bytes(namespace, canonical(value))
        refs[name] = {"id": MODEL_ID, "path": ref.path, "sha256": ref.sha256}
    model_sha = refs["model"]["sha256"]
    return {
        "format": "gridoracle-model-bundle-v1",
        **refs,
        "artifacts": [refs[key] for key in sorted(refs)],
        "model_manifest_id": f"{MODEL_ID}/{model_sha[:16]}",
        "dataset_id": DATASET_ID,
        "feature_snapshot_id": FEATURE_SNAPSHOT_ID,
        "calibrator_manifest_id": f"{MODEL_ID}/{model_sha[:16]}/identity",
        "code_revision": code_revision,
        "runtime_image": runtime_image,
    }


def write(artifacts: Path, bundles: Path, runtime_image: str, code_revision: str):
    if "@sha256:" not in runtime_image:
        raise ValueError("runtime image must be pinned by version and digest")
    bundle = closure(
        ContentAddressedArtifactStore(artifacts), runtime_image, code_revision
    )
    raw = canonical(bundle)
    digest = sha256(raw).hexdigest()
    target = bundles / f"{digest}.json"
    if not target.exists():
        temporary = bundles / f".{digest}.tmp"
        temporary.write_bytes(raw)
        os.replace(temporary, target)
    verify_bundle(artifacts, target, digest)
    return digest


def register(engine, artifacts: Path, bundle_file: Path, bundle_sha256: str) -> None:
    bundle = verify_bundle(artifacts, bundle_file, bundle_sha256)
    store = ImmutableProvenanceStore(engine, ContentAddressedArtifactStore(artifacts))
    with engine.begin() as conn:
        version = conn.execute(
            text("SELECT id FROM model_versions WHERE name=:name ORDER BY id LIMIT 1"),
            {"name": MODEL_VERSION_NAME},
        ).scalar_one_or_none()
        if version is None:
            version = conn.execute(
                text(
                    "INSERT INTO model_versions (name, trained_at, "
                    "training_races_count, notes) VALUES (:name, :at, 0, :notes) "
                    "RETURNING id"
                ),
                {
                    "name": MODEL_VERSION_NAME,
                    "at": datetime.now(UTC),
                    "notes": "Fixed baselines; nothing is fitted",
                },
            ).scalar_one()
    data = bundle["training_data"]
    store.record_dataset(
        dataset_id=bundle["dataset_id"],
        artifact_path=data["path"],
        sha256=data["sha256"],
        manifest={"fit": "none"},
    )
    schema = bundle["feature_schema"]
    store.record_feature_snapshot(
        feature_snapshot_id=bundle["feature_snapshot_id"],
        dataset_id=bundle["dataset_id"],
        artifact_path=schema["path"],
        sha256=schema["sha256"],
        manifest={"role": "feature schema"},
    )
    model = bundle["model"]
    store.record_model_manifest(
        model_manifest_id=bundle["model_manifest_id"],
        model_id=model["id"],
        model_version_id=version,
        artifact_path=model["path"],
        sha256=model["sha256"],
        manifest={"format": MODEL["format"]},
    )
    calibration = bundle["calibration"]
    store.record_calibrator_manifest(
        calibrator_manifest_id=bundle["calibrator_manifest_id"],
        model_manifest_id=bundle["model_manifest_id"],
        artifact_path=calibration["path"],
        sha256=calibration["sha256"],
        manifest=CALIBRATION,
    )
    verify_selection(engine, bundle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    writer = sub.add_parser("write", help="write the closure and the bundle file")
    writer.add_argument("--bundles", type=Path, required=True)
    writer.add_argument("--runtime-image", required=True)
    writer.add_argument("--code-revision", required=True)
    sub.add_parser("register", help="record the configured bundle's manifests")
    args = parser.parse_args()
    artifacts = Path(os.environ["GRIDORACLE_ARTIFACT_ROOT"])
    if args.action == "write":
        digest = write(artifacts, args.bundles, args.runtime_image, args.code_revision)
        print(json.dumps({"bundle_sha256": digest}))
        return
    configure()
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        register(
            engine,
            artifacts,
            Path(os.environ["GRIDORACLE_BUNDLE_FILE"]),
            os.environ["GRIDORACLE_BUNDLE_SHA256"],
        )
    finally:
        engine.dispose()
    print(json.dumps({"registered": os.environ["GRIDORACLE_BUNDLE_SHA256"]}))


if __name__ == "__main__":
    main()
