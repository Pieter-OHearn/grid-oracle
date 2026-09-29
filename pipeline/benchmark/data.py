"""Verify WP05 inputs and reconstruct features independently of target access."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline.benchmark.artifacts import ROOT, digest, file_hash, read_json
from pipeline.dataset.historical import DatasetBackfill, FeatureHorizon

DATASET = ROOT / "docs/datasets/versions/dataset-2026.2-wp05-87d0a99ef821-9f459a82d698"
DATASET_HASH = "6ff6b63b470900cb1d55513d91e9362851948d04133b8cd2b216bb7dccf671d2"
ARCHIVE = ROOT / "docs/evidence/jolpica-2022-2025.tar.gz"
KEY = "driver_identity_key"


def load_dataset(scratch: Path) -> tuple[dict[str, pd.DataFrame], dict, dict]:
    if file_hash(DATASET / "manifest.json") != DATASET_HASH:
        raise ValueError("WP05 manifest drift")
    builder = DatasetBackfill.from_jolpica_archive(ARCHIVE)
    rebuilt = builder.write(scratch)
    if rebuilt["manifest_sha256"] != DATASET_HASH:
        raise ValueError("WP05 reconstruction drift")
    frames = {h.value: [] for h in FeatureHorizon}
    for part in rebuilt["outputs"]:
        path = Path(rebuilt["root"]) / part["path"]
        if file_hash(path) != part["parquet_sha256"]:
            raise ValueError("WP05 partition drift")
        frames[part["session"]].append(pd.read_parquet(path))
    features = {h: pd.concat(parts, ignore_index=True) for h, parts in frames.items()}
    # Pinned WP05 reconciliation owns status classification and conflict quarantine.
    results, _, _ = builder._reconcile()
    targets = target_records(results)
    manifest = dataset_manifest(builder, features, targets, results)
    return features, targets, manifest


def target_records(results: pd.DataFrame) -> dict:
    targets = {}
    for race, rows in results.groupby("race_key"):
        targets[race] = [
            {
                "driver": row.driver_identity_key,
                "rank": int(row.finish_position) if row.target_eligible else None,
                "status": row.canonical_status,
                "team": row.constructor_identity_key,
            }
            for row in rows.sort_values(KEY).itertuples()
        ]
    return targets


def circuits(builder: DatasetBackfill) -> dict[str, str]:
    result = {}
    for snapshot in builder.snapshots:
        for race in json.loads(snapshot.payload)["MRData"]["RaceTable"]["Races"]:
            result[f"{race['season']}:{race['round']}"] = race["Circuit"]["circuitId"]
    return result


def dataset_manifest(builder: DatasetBackfill, features: dict, targets: dict, results: pd.DataFrame) -> dict:
    circuit = circuits(builder)
    races = []
    for race, rows in results.groupby("race_key", sort=False):
        first = rows.iloc[0]
        races.append(
            {
                "race": race,
                "season": int(first.season),
                "round": int(first["round"]),
                "event_at": first.event_at.isoformat(),
                "circuit": circuit[race],
                "drivers": sorted(rows[KEY].tolist()),
                "target_sha256": digest(targets[race]),
            }
        )
    return {
        "version": "wp06-v1",
        "quality": "explored_chronological_reconstruction_not_asof",
        "wp05_manifest_sha256": DATASET_HASH,
        "archive_sha256": file_hash(ARCHIVE),
        "target_policy_version": "2026.1",
        "target_implementation_sha256": file_hash(ROOT / "gridoracle/domain/results.py"),
        "feature_contract_sha256": read_json(DATASET / "manifest.json")["feature_contract_sha256"],
        "horizon_rows": {h: len(frame) for h, frame in features.items()},
        "asof_eligible_rows": 0,
        "races": sorted(races, key=lambda race: race["event_at"]),
    }
