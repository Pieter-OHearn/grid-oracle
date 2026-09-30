"""PR #99 adversarial regressions across the public benchmark adapters."""

from __future__ import annotations

import copy
import math

import numpy as np
import pandas as pd
import pytest

from pipeline.benchmark.artifacts import BENCHMARK, CONTRACT, digest, read_json, write_bytes_once, write_once
from pipeline.benchmark.baselines import predict
from pipeline.benchmark.data import KEY, load_dataset
from pipeline.benchmark.evaluation import evaluate_predictions
from pipeline.benchmark.fitting import fit_calibrator, fit_in_block
from pipeline.benchmark.metrics import score_race
from pipeline.benchmark.registry import Registry
from pipeline.benchmark.splits import make_splits, validate_splits
from pipeline.benchmark.temporal import TemporalViolation, validate_feature_time, validate_features


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    return load_dataset(tmp_path_factory.mktemp("wp06-review"))


@pytest.fixture
def config():
    return read_json(CONTRACT / "config.json")


def fitting_case(data, kind):
    frames, targets, dataset = data
    splits = make_splits(dataset)
    key = splits["folds"][0]["train" if kind == "model" else "calibration"][0]
    frame = frames["pre_weekend"]
    frame = frame[frame.race_key == key].copy()
    labels = pd.DataFrame(
        [{"race_key": key, KEY: row["driver"], "target": int(row["rank"] == 1)} for row in targets[key]]
    )
    predictions = {key: dict.fromkeys(frame[KEY], 1 / len(frame))}
    return frame, labels, predictions, dataset, splits


def fit_case(kind, frame, labels, predictions, dataset, splits, **kwargs):
    calls = []
    if kind == "model":
        fit_in_block(
            lambda x, y: calls.append((x, y)),
            frame,
            labels,
            dataset=dataset,
            splits=splits,
            fold_id=kwargs.pop("fold_id", "2023"),
            purpose="train",
            horizon="pre_weekend",
            feature_names=["driver_finish_mean_last_3"],
            **kwargs,
        )
    else:
        fit_calibrator(
            lambda x, y: calls.append((x, y)),
            predictions,
            labels,
            dataset=dataset,
            splits=splits,
            fold_id=kwargs.pop("fold_id", "2023"),
            **kwargs,
        )
    return calls


@pytest.mark.parametrize("baseline", ["standings", "recent_form", "qualifying"])
def test_tied_winner_has_equal_strength_and_uniform_loss(data, config, baseline):
    horizon = "post_qualifying" if baseline == "qualifying" else "pre_weekend"
    frame = data[0][horizon]
    frame = frame[frame.race_key == "2023:1"].copy()
    for field in (
        "driver_championship_position_race_only",
        "driver_finish_mean_last_3",
        "constructor_finish_mean_last_3",
        "qualifying_position",
    ):
        if field in frame:
            frame[field] = 1
    result = predict(frame, baseline, horizon, config["rank_temperature"])
    assert len(set(result["winner"].values())) == 1
    score = score_race(data[1]["2023:1"], result, frame[KEY].tolist(), config)
    assert score["winner_log_loss"] == pytest.approx(math.log(len(frame)))


def test_partial_ties_share_mean_rank_and_ignore_driver_name(data, config):
    frame = data[0]["pre_weekend"]
    frame = frame[frame.race_key == "2023:1"].iloc[:3].copy()
    frame[KEY] = ["z", "a", "m"]
    frame["driver_championship_position_race_only"] = [1, 1, 3]
    result = predict(frame, "standings", "pre_weekend", 4)
    weights = np.exp(-np.array([0.5, 0.5, 2]) / 4)
    assert result["winner"]["a"] == result["winner"]["z"] == pytest.approx(weights[0] / weights.sum())
    assert result["order"] == ["a", "z", "m"]
    frame[KEY] = ["b", "x", "m"]
    renamed = predict(frame, "standings", "pre_weekend", 4)
    assert renamed["winner"]["b"] == result["winner"]["z"]


@pytest.mark.parametrize(
    "key,value",
    [("epsilon", 0.5), ("block_races", 70), ("seed", 1), ("bootstrap_replicates", 2), ("rank_temperature", 1)],
)
def test_public_evaluation_rejects_modified_config(data, config, key, value):
    _, targets, dataset = data
    config[key] = value
    with pytest.raises(ValueError, match="config differs"):
        evaluate_predictions({}, targets, dataset, make_splits(dataset), config)


@pytest.mark.parametrize("mutation", ["shrink", "empty", "relabel"])
def test_public_evaluation_cannot_shrink_or_relabel_registered_cohort(data, config, mutation):
    _, targets, dataset = copy.deepcopy(data)
    splits = make_splits(dataset)
    if mutation == "shrink":
        splits["folds"][0]["evaluation"] = splits["folds"][0]["evaluation"][:-10]
    elif mutation == "empty":
        splits["folds"] = []
    else:
        targets["2023:1"][0]["rank"] = 1
        next(r for r in dataset["races"] if r["race"] == "2023:1")["target_sha256"] = digest(targets["2023:1"])
        splits = make_splits(dataset)
    with pytest.raises(ValueError, match="differs from registered lock"):
        evaluate_predictions({}, targets, dataset, splits, config)


def test_evaluation_returns_verified_fingerprints(data, config):
    output = evaluate_predictions({}, data[1], data[2], make_splits(data[2]), config)
    assert output["input_fingerprints"]["dataset_sha256"] == digest(data[2])
    assert output["input_fingerprints"]["split_sha256"] == digest(make_splits(data[2]))
    assert output["input_fingerprints"]["lock_sha256"]


@pytest.mark.parametrize("fold_id", [2023, None, "", ["2023"]])
def test_non_string_or_empty_fold_ids_rejected(data, fold_id):
    splits = make_splits(data[2])
    splits["folds"][0]["id"] = fold_id
    with pytest.raises(ValueError, match="fold ids"):
        validate_splits(splits, data[2])


def test_duplicate_fold_ids_and_empty_folds_rejected(data):
    splits = make_splits(data[2])
    splits["folds"][1]["id"] = splits["folds"][0]["id"]
    with pytest.raises(ValueError, match="fold ids"):
        validate_splits(splits, data[2])
    splits["folds"] = []
    with pytest.raises(ValueError, match="empty folds"):
        validate_splits(splits, data[2])


@pytest.mark.parametrize("kind", ["model", "calibrator"])
@pytest.mark.parametrize("mutation", ["config", "calibration_recut", "labels", "dataset"])
def test_fitting_inputs_are_bound_to_registered_contract(data, config, kind, mutation):
    frame, labels, predictions, dataset, splits = fitting_case(data, kind)
    dataset = copy.deepcopy(dataset)
    if mutation == "config":
        config["epsilon"] = 0.5
    elif mutation == "calibration_recut":
        fold = splits["folds"][0]
        fold["calibration"] = fold["evaluation"][:4]
        fold["evaluation"] = fold["evaluation"][4:]
    elif mutation == "labels":
        winner = labels.index[labels.target == 1][0]
        other = labels.index[labels.target == 0][0]
        labels.loc[winner, "target"] = 0
        labels.loc[other, "target"] = 1
    else:
        dataset["races"][0]["target_sha256"] = "modified"
        splits = make_splits(dataset)
    with pytest.raises(ValueError, match="differs"):
        fit_case(kind, frame, labels, predictions, dataset, splits, config=config)


@pytest.mark.parametrize("kind", ["model", "calibrator"])
@pytest.mark.parametrize("cutoff", [None, "2099-01-01T00:00:00+00:00"])
def test_future_label_timestamps_rejected_without_caller_cutoff(data, kind, cutoff):
    case = fitting_case(data, kind)
    case[1]["available_at"] = "2098-01-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="unavailable|cutoff differs"):
        fit_case(kind, *case, evaluation_cutoff=cutoff)


@pytest.mark.parametrize("kind", ["model", "calibrator"])
@pytest.mark.parametrize("fold_id", ["2023 ", 2023, "2O24"])
def test_unknown_fold_is_a_value_error_not_stop_iteration(data, kind, fold_id):
    with pytest.raises(ValueError, match="unknown fold_id"):
        fit_case(kind, *fitting_case(data, kind), fold_id=fold_id)


@pytest.mark.parametrize("kind", ["model", "calibrator"])
def test_verified_fitting_inputs_still_work(data, kind):
    case = fitting_case(data, kind)
    case[1]["available_at"] = "2022-12-31T00:00:00+00:00"
    calls = fit_case(kind, *case)
    assert len(calls) == 1
    assert sum(calls[0][1]) == 1


@pytest.mark.parametrize("mutation", ["duplicate", "overwrite"])
def test_duplicate_or_overwritten_feature_cannot_enter_estimator(data, mutation):
    frame, labels, predictions, dataset, splits = fitting_case(data, "model")
    if mutation == "duplicate":
        frame = pd.concat([frame, frame[["driver_finish_mean_last_3"]].fillna(1)], axis=1)
    else:
        frame["driver_finish_mean_last_3"] = 1
    with pytest.raises(ValueError, match="duplicate feature|values differ"):
        fit_case("model", frame, labels, predictions, dataset, splits)


def test_proof_copied_from_later_race_fails_pinned_time_check(data):
    frame = data[0]["pre_weekend"].iloc[:1].copy()
    frame["asof_eligible"] = True
    frame["entry_provenance"] = "verified_entry_list"
    frame["cutoff"] = "2022-03-21T00:00:00+00:00"
    key = f"{frame.iloc[0].race_key}/{frame.iloc[0][KEY]}"
    proof = {
        key: {"first_competitive_session_at": "2022-03-25T00:00:00+00:00", "race_start_at": "2022-03-27T17:00:00+00:00"}
    }
    with pytest.raises(TemporalViolation, match="differs from pinned race"):
        validate_features(frame, "pre_weekend", evidence=proof, dataset=data[2])
    with pytest.raises(TemporalViolation, match="pinned race times"):
        validate_features(frame, "pre_weekend", evidence=proof)


def test_qualifying_substring_does_not_exempt_historical_feature():
    from datetime import datetime

    first = datetime.fromisoformat("2027-03-01T00:00:00+00:00")
    cutoff = datetime.fromisoformat("2027-03-04T00:00:00+00:00")
    proof = dict.fromkeys(("event_at", "available_at", "retrieved_at"), "2027-03-02T00:00:00+00:00")
    with pytest.raises(TemporalViolation, match="current/future race"):
        validate_feature_time("historical_qualifying_mean", proof, cutoff, first, "post_qualifying")


@pytest.mark.parametrize("bad", [float("nan"), np.int64(300)])
def test_serialization_failure_leaves_no_poisoned_artifact(tmp_path, bad):
    target = tmp_path / "artifact.json"
    with pytest.raises((ValueError, TypeError)):
        write_once(target, {"value": bad})
    assert not target.exists()
    write_once(target, {"value": 300})
    assert read_json(target) == {"value": 300}


def test_failed_finish_can_then_be_recorded_as_failure(tmp_path):
    registry = Registry(tmp_path)
    identifier = registry.start({})
    with pytest.raises(ValueError):
        registry.finish(identifier, result={"loss": float("nan")})
    registry.finish(identifier, error=ValueError("nonfinite metric"))
    assert read_json(tmp_path / identifier / "finished.json")["status"] == "failed"
    with pytest.raises(TypeError):
        registry.start({"n": np.int64(300)})
    assert len(registry.records()) == 1


def test_atomic_write_failure_and_existing_file_leave_bytes_intact(tmp_path, monkeypatch):
    import pipeline.benchmark.artifacts as artifacts

    target = tmp_path / "report.json.gz"
    with monkeypatch.context() as patch:
        patch.setattr(artifacts.os, "link", lambda *args: (_ for _ in ()).throw(OSError("interrupted publication")))
        with pytest.raises(OSError):
            write_bytes_once(target, b"complete bytes")
    assert not target.exists()
    assert not list(tmp_path.glob(".benchmark-*"))
    write_bytes_once(target, b"complete bytes")
    with pytest.raises(FileExistsError):
        write_bytes_once(target, b"different")
    assert target.read_bytes() == b"complete bytes"


@pytest.mark.parametrize("phase", ["config", "metadata", "checksum"])
def test_early_run_failure_is_a_registered_failed_attempt(tmp_path, monkeypatch, phase):
    import pipeline.benchmark.__main__ as cli

    def fail(*args, **kwargs):
        raise ValueError(f"injected {phase} failure")

    monkeypatch.setattr(cli, {"config": "read_json", "metadata": "metadata", "checksum": "file_hash"}[phase], fail)
    with pytest.raises(ValueError, match=f"injected {phase}"):
        cli.run(tmp_path)
    events = list((tmp_path / "experiments").glob("*/finished.json"))
    assert len(events) == 1
    assert read_json(events[0])["status"] == "failed"
    assert (events[0].parent / "started.json").is_file()


def test_failure_recording_does_not_mask_original_error(tmp_path, monkeypatch):
    import pipeline.benchmark.__main__ as cli

    def broken_prepare(*args):
        raise ValueError("original preparation failure")

    def broken_finish(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(cli, "prepare", broken_prepare)
    monkeypatch.setattr(cli.Registry, "finish", broken_finish)
    with pytest.raises(ValueError, match="original preparation") as caught:
        cli.run(tmp_path)
    assert "disk unavailable" in caught.value.__notes__[0]
    assert len(list((tmp_path / "experiments").glob("*/started.json"))) == 1


def test_v1_protocol_and_all_tolerances_are_preserved():
    old = read_json(BENCHMARK / "config.json")
    new = read_json(CONTRACT / "config.json")
    assert new.pop("tie_policy") == "mean_rank"
    assert new.pop("protocol_version") == "wp06-v2"
    old.pop("protocol_version")
    assert old == new
    lock = read_json(BENCHMARK / "lock.json")
    from pipeline.benchmark.artifacts import ROOT, file_hash

    for name, expected in lock["files"].items():
        assert file_hash(ROOT / name) == expected
