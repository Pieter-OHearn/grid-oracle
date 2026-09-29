"""Frozen forward splits and whole-race fit boundaries."""

from __future__ import annotations

from datetime import datetime

from pipeline.benchmark.artifacts import digest

BLOCKS = ("train", "tune", "calibration", "evaluation")


def make_splits(dataset: dict) -> dict:
    races = dataset["races"]
    folds = []
    for year in (2023, 2024, 2025):
        past = [r["race"] for r in races if r["season"] < year]
        folds.append(
            {
                "id": str(year),
                "train": past[:-8],
                "tune": past[-8:-4],
                "calibration": past[-4:],
                "evaluation": [r["race"] for r in races if r["season"] == year],
            }
        )
    manifest = {
        "version": "wp06-v1",
        "dataset_sha256": digest(dataset),
        "folds": folds,
        "prospective": {
            "status": "pending_calendar_enrollment",
            "seasons": [2027, 2028],
            "races": [],
            "enroll_days_before_first_event": 30,
            "policy": "All scheduled Grands Prix; freeze calendars before outcomes; no retrospective enrollment.",
        },
    }
    validate_splits(manifest, dataset)
    return manifest


def validate_splits(manifest: dict, dataset: dict) -> None:
    if manifest["dataset_sha256"] != digest(dataset):
        raise ValueError("split dataset mismatch")
    races = {r["race"]: r for r in dataset["races"]}
    evaluated = set()
    for fold in manifest["folds"]:
        seen = set()
        end = None
        for block in BLOCKS:
            keys = fold[block]
            if not keys or len(set(keys)) != len(keys) or seen.intersection(keys):
                raise ValueError("empty, duplicate or overlapping race block")
            if not set(keys) <= races.keys():
                raise ValueError("unknown race in split")
            times = [datetime.fromisoformat(races[k]["event_at"]) for k in keys]
            if times != sorted(times) or len(set(times)) != len(times) or (end and min(times) <= end):
                raise ValueError("nonchronological split")
            end = max(times)
            seen.update(keys)
        if evaluated.intersection(fold["evaluation"]):
            raise ValueError("race evaluated twice")
        evaluated.update(fold["evaluation"])


def validate_fit_rows(rows: list[tuple[str, str]], fold: dict, dataset: dict, purpose: str) -> None:
    scopes = {"train": ["train"], "tune": ["tune"], "refit": ["train", "tune"], "calibration": ["calibration"]}
    if purpose not in scopes:
        raise ValueError("unknown fitting purpose")
    allowed = {race for block in scopes[purpose] for race in fold[block]}
    if len(set(rows)) != len(rows) or not rows:
        raise ValueError("duplicate or empty fitting rows")
    selected = {race for race, _ in rows}
    if not selected <= allowed:
        raise ValueError("fitting outside the declared temporal block")
    fields = {r["race"]: r["drivers"] for r in dataset["races"]}
    expected = {(race, driver) for race in selected for driver in fields[race]}
    if set(rows) != expected:
        raise ValueError("a race field was split during fitting")


def validate_label_availability(available_at: list[str], evaluation_cutoff: str) -> None:
    cutoff = datetime.fromisoformat(evaluation_cutoff)
    if not cutoff.tzinfo or not available_at:
        raise ValueError("missing timezone-aware label availability")
    for value in available_at:
        timestamp = datetime.fromisoformat(value)
        if not timestamp.tzinfo or timestamp >= cutoff:
            raise ValueError("fitting labels unavailable before evaluation")
