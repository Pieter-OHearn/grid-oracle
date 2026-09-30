"""Paired whole-race and consecutive block resampling, never driver resampling."""

from __future__ import annotations

import numpy as np


def assert_paired(reference: list[dict], candidate: list[dict]) -> None:
    def keys(rows: list[dict]) -> list[tuple]:
        return [(r["race"], r["fold"], r["cohort_sha256"], r["target_sha256"]) for r in rows]

    if keys(reference) != keys(candidate) or len({r["race"] for r in reference}) != len(reference):
        raise ValueError("paired uncertainty requires identical ordered race, entry and target cohorts")


def block_units(records: list[dict], size: int) -> list[list[int]]:
    if records and all("block" in r for r in records):
        return [
            [i for i, row in enumerate(records) if row["block"] == block]
            for block in dict.fromkeys(r["block"] for r in records)
        ]
    units = []
    for fold in dict.fromkeys(r["fold"] for r in records):
        indices = [i for i, r in enumerate(records) if r["fold"] == fold]
        units.extend(indices[i : i + size] for i in range(0, len(indices), size))
    return units


def bootstrap(values: np.ndarray, units: list[list[int]], config: dict) -> dict:
    result = {"mean": float(values.mean()) if len(values) else None, "ci95": None, "units": len(units)}
    if len(units) < 2:
        return result
    rng = np.random.default_rng(config["seed"])
    sums = np.array([values[u].sum() for u in units])
    sizes = np.array([len(u) for u in units])
    indices = rng.integers(0, len(units), size=(config["bootstrap_replicates"], len(units)))
    samples = sums[indices].sum(axis=1) / sizes[indices].sum(axis=1)
    result["ci95"] = np.quantile(samples, [0.025, 0.975]).tolist()
    return result


def uncertainty(records: list[dict], config: dict, reference: list[dict] | None = None) -> dict:
    if reference is not None:
        assert_paired(reference, records)
    values = [r["winner_log_loss"] for r in records]
    other = [r["winner_log_loss"] for r in reference] if reference is not None else []
    if not values or any(v is None for v in [*values, *other]):
        return {"race": None, "block": None, "reason": "missing evaluation; no silent pair deletion"}
    array = np.array(values)
    if reference is not None:
        array = np.array(other) - array
    return {
        "race": bootstrap(array, [[i] for i in range(len(records))], config),
        "block": bootstrap(array, block_units(records, config["block_races"]), config),
        "sign": "reference_minus_candidate" if reference is not None else "loss",
    }
