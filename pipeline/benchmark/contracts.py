"""Library entry-point checks against registered inputs, never caller-defined locks."""

from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from pipeline.benchmark.artifacts import BENCHMARK, CONTRACT, ROOT, canonical, digest, file_hash, read_json, verify_lock
from pipeline.benchmark.data import ARCHIVE, DATASET, DATASET_HASH, KEY, target_records
from pipeline.dataset.historical import DatasetBackfill


def verify_inputs(dataset: dict, splits: dict, config: dict | None = None) -> dict:
    """Verify file bytes first, then semantic equality of caller-supplied objects."""
    lock = verify_lock()
    hashes = {"lock_sha256": file_hash(CONTRACT / "lock.json")}
    for name, value, path in (
        ("dataset", dataset, BENCHMARK / "dataset.json"),
        ("split", splits, BENCHMARK / "splits.json"),
        ("config", config, CONTRACT / "config.json"),
    ):
        relative = path.relative_to(ROOT).as_posix()
        if relative not in lock["files"]:
            raise ValueError(f"registered lock omits {name}")
        frozen = read_json(path)
        if value is not None and digest(value) != digest(frozen):
            raise ValueError(f"{name} differs from registered lock")
        hashes[f"{name}_sha256"] = lock["files"][relative]
    return hashes


def verified_wp05_manifest(dataset: dict) -> dict:
    path = DATASET / "manifest.json"
    if file_hash(path) != DATASET_HASH or dataset["wp05_manifest_sha256"] != DATASET_HASH:
        raise ValueError("WP05 manifest differs from frozen dataset")
    return read_json(path)


def verify_feature_values(frame: pd.DataFrame, horizon: str, dataset: dict) -> None:
    """Compare supplied historical rows to checksum-verified WP05 partitions."""
    manifest = verified_wp05_manifest(dataset)
    parts = []
    for part in manifest["outputs"]:
        if part["session"] != horizon:
            continue
        path = DATASET / part["path"]
        if file_hash(path) != part["parquet_sha256"]:
            raise ValueError("WP05 feature partition checksum mismatch")
        parts.append(pd.read_parquet(path))
    frozen = pd.concat(parts, ignore_index=True).set_index(["race_key", KEY])
    actual = frame.set_index(["race_key", KEY])
    if not set(actual.index) <= set(frozen.index):
        raise ValueError("feature identities absent from frozen partitions")
    expected = frozen.loc[actual.index, actual.columns]
    try:
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, check_exact=True)
    except AssertionError as error:
        raise ValueError("feature values differ from frozen WP05 partitions") from error


@lru_cache(maxsize=2)
def _source_targets(archive_hash: str, feature_hash: str, target_hash: str) -> bytes:
    """Cache immutable bytes; verify sources before every call into this cache."""
    builder = DatasetBackfill.from_jolpica_archive(ARCHIVE)
    if builder._feature_contract_hash() != feature_hash:
        raise ValueError("WP05 reconciliation implementation drift")
    results, _, _ = builder._reconcile()
    return canonical(target_records(results))


def verified_targets(dataset: dict) -> dict:
    verified_wp05_manifest(dataset)
    archive_hash = file_hash(ARCHIVE)
    target_hash = file_hash(ROOT / "gridoracle/domain/results.py")
    feature_hash = dataset["feature_contract_sha256"]
    if archive_hash != dataset["archive_sha256"] or target_hash != dataset["target_implementation_sha256"]:
        raise ValueError("frozen target source changed")
    # Verify implementation even when labels are cached.
    if DatasetBackfill(())._feature_contract_hash() != feature_hash:
        raise ValueError("WP05 reconciliation implementation drift")
    targets = json.loads(_source_targets(archive_hash, feature_hash, target_hash))
    for race in dataset["races"]:
        if digest(targets[race["race"]]) != race["target_sha256"]:
            raise ValueError("source labels differ from frozen target hash")
    return targets


def verify_label_values(labels: pd.DataFrame, dataset: dict, target_kind: str) -> None:
    if target_kind not in {"winner", "rank"}:
        raise ValueError("target_kind must be winner or rank")
    targets = verified_targets(dataset)
    for race, rows in labels.groupby("race_key", sort=False):
        classified = sorted((r for r in targets[race] if r["rank"] is not None), key=lambda r: r["rank"])
        if not classified or classified[0]["rank"] != 1:
            raise ValueError("fitting race has no verified winner")
        ranks = {row["driver"]: index + 1 for index, row in enumerate(classified)}
        winner = classified[0]["driver"]
        for row in rows.to_dict("records"):
            expected = int(row[KEY] == winner) if target_kind == "winner" else ranks.get(row[KEY])
            actual = None if pd.isna(row["target"]) else row["target"]
            if actual != expected:
                raise ValueError("fitting label differs from frozen target")
