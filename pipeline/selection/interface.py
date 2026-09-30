"""Stable model interface over immutable, hash-checked WP07/WP08 artifacts."""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

from pipeline.benchmark.artifacts import digest, file_hash
from pipeline.benchmark.baselines import predict as baseline_predict
from pipeline.benchmark.data import KEY
from pipeline.benchmark.temporal import validate_features
from pipeline.challengers.decoder import calibrate, decode
from pipeline.challengers.models import ForecastModel
from pipeline.selection.outputs import Field


class Candidate(Protocol):
    identity: str
    horizon: str
    lineage: dict

    def predict(self, frame: pd.DataFrame, field: Field) -> dict: ...


def check_frame(frame, field, horizon):
    validate_features(frame, horizon)
    if horizon != field.horizon or set(frame.race_key) != {field.race} or set(frame[KEY]) != set(field.entries):
        raise ValueError("candidate horizon/race/entry field mismatch")
    if "constructor_identity_key" in frame:
        teams = tuple(sorted(zip(frame[KEY], frame.constructor_identity_key, strict=True)))
        if field.teams != teams:
            raise ValueError("constructor assignment differs from frozen entry revision")
    if set(frame.cutoff) != {field.cutoff}:
        raise ValueError("candidate cutoff differs from frozen field")


def checked_file(path: Path, expected: str):
    if file_hash(path) != expected:
        raise ValueError(f"artifact checksum mismatch: {path.name}")


@dataclass
class Baseline:
    identity: str
    horizon: str
    lineage: dict

    def __post_init__(self):
        self.lineage = {**self.lineage, "calibrator_sha256": digest({"method": "identity", "protocol": "wp06-v2"})}

    def predict(self, frame, field):
        check_frame(frame, field, self.horizon)
        result = baseline_predict(frame, self.identity, self.horizon, 4.0)
        field.check(result)
        return result


class Classical:
    def __init__(self, path: Path, expected_sha256: str, horizon: str):
        checked_file(path, expected_sha256)
        self.artifact = json.loads(gzip.decompress(path.read_bytes()))
        parts = self.artifact["candidate"].split("__")
        if parts[0] != horizon:
            raise ValueError("artifact horizon mismatch")
        self.identity = "__".join(parts[1:-1])
        self.horizon = horizon
        self.model = ForecastModel.restore(self.artifact["model"])
        self.power = self.artifact["decoder"]["power"]
        self.lineage = {
            "model_sha256": expected_sha256,
            "artifact_sha256": digest(self.artifact),
            "calibrator_sha256": digest(self.artifact["decoder"]),
            "fit_races": self.artifact["fit_races"],
            "calibration_races": self.artifact["calibration_races"],
        }

    def raw(self, frame, field):
        check_frame(frame, field, self.horizon)
        return decode(frame[KEY].tolist(), self.model.scores(frame))

    def predict(self, frame, field):
        result = calibrate(self.raw(frame, field), self.power)
        field.check(result)
        return result


class Custom:
    def __init__(self, path: Path, expected_sha256: str, decision: dict, races: dict):
        # Optional torch is imported only when a custom artifact is requested.
        from pipeline.custom_model.training import load

        checked_file(path, expected_sha256)
        self.model, self.encoder, self.state = load(path)
        self.horizon = decision["horizon"]
        self.identity = "wp08_" + decision["family"]
        self.temperature = decision["temperature"]
        if path.name != f"{self.horizon}-{decision['family']}-{decision['fold']}.pt":
            raise ValueError("custom model alias differs from decision")
        self.races = races
        self.lineage = {"model_sha256": expected_sha256, "calibrator_sha256": digest(decision)}

    def raw(self, frame, field):
        from pipeline.custom_model.experiment import predict

        check_frame(frame, field, self.horizon)
        return predict(self.model, self.encoder, frame, self.races, "cpu")[field.race]

    def predict(self, frame, field):
        from pipeline.custom_model.experiment import predict

        check_frame(frame, field, self.horizon)
        result = predict(self.model, self.encoder, frame, self.races, "cpu", self.temperature)[field.race]
        field.check(result)
        return result
