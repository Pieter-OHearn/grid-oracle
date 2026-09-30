"""WP07 direction, grouping, calibration, optimizer and frozen-boundary tests."""

import gzip
import json

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import check_grad

from pipeline.benchmark.artifacts import BENCHMARK, CONTRACT, ROOT, digest, read_json, verify_lock
from pipeline.benchmark.baselines import predict as baseline_predict
from pipeline.benchmark.data import DATASET, KEY
from pipeline.challengers import __main__ as cli
from pipeline.challengers.decoder import calibrate, choose_power, decode
from pipeline.challengers.models import TEAM, Encoder, ForecastModel, pl_objective, race_weights, rank_groups
from pipeline.challengers.study import feature_names, fit_model, label_frame, ordered_block, predictions

STUDY = read_json(ROOT / "docs/models/wp07/config.json")


@pytest.fixture(scope="module")
def frozen():
    from pipeline.benchmark.contracts import verified_targets

    manifest = read_json(DATASET / "manifest.json")
    frames = {
        h: pd.concat(
            [pd.read_parquet(DATASET / p["path"]) for p in manifest["outputs"] if p["session"] == h], ignore_index=True
        )
        for h in ("pre_weekend", "post_qualifying")
    }
    dataset = read_json(BENCHMARK / "dataset.json")
    return (
        frames,
        verified_targets(dataset),
        dataset,
        read_json(BENCHMARK / "splits.json"),
        read_json(CONTRACT / "config.json"),
    )


def test_decoder_matches_wp06_mean_ties():
    frame = pd.DataFrame(
        {
            KEY: ["c", "b", "a"],
            "race_key": "r",
            "horizon": "pre_weekend",
            "missing__qualifying": True,
            "driver_championship_position_race_only": [3.0, 1.0, 1.0],
        }
    )
    baseline = baseline_predict(frame, "standings", "pre_weekend", 4)
    prediction = decode(frame[KEY].tolist(), -frame.driver_championship_position_race_only.to_numpy())
    assert prediction["order"] == ["a", "b", "c"]
    assert prediction["winner"] == baseline["winner"]
    assert prediction["winner"]["a"] == prediction["winner"]["b"]
    for power in STUDY["decoder"]["calibration_powers"]:
        output = calibrate(prediction, power)
        assert output["order"] == prediction["order"]
        assert sum(output["winner"].values()) == pytest.approx(1)
        assert output["winner"]["a"] == output["winner"]["b"]


@pytest.mark.parametrize("scores,temp", [([np.nan, 1], 4), ([1, np.inf], 4), ([1, 2], 0), ([1, 2], np.inf)])
def test_decoder_rejects_invalid(scores, temp):
    with pytest.raises(ValueError):
        decode(["a", "b"], scores, temp)


def test_power_calibration_equal_race_weight():
    result = choose_power([0.8, 0.2, 0.6, 0.3, 0.1], [1, 0, 0, 0, 1], [2, 3], [0.5, 1, 2])
    assert result["trials"][1]["winner_log_loss"] == pytest.approx((-np.log(0.8) - np.log(0.1)) / 2)
    assert result["power"] == 0.5


def test_ranking_direction_and_query_boundaries():
    frame = pd.DataFrame({"race_key": ["r1"] * 4 + ["r2"] * 3})
    indices, qids, relevance = rank_groups(frame, np.array([3, 1, np.nan, 2, 1, 2, 3]))
    assert indices.tolist() == [0, 1, 3, 4, 5, 6]
    assert qids.tolist() == [0, 0, 0, 1, 1, 1]
    assert relevance.tolist() == [0, 2, 1, 2, 1, 0]


def test_pl_gradient_and_label_direction():
    x = np.array([[2.0, 1.0], [0.0, 1.0], [-1.0, 0.0]])
    args = (x, [np.array([0, 1, 2])], [1.0], 0.1)
    beta = np.array([0.2, -0.3])
    error = check_grad(lambda b: pl_objective(b, *args)[0], lambda b: pl_objective(b, *args)[1], beta)
    assert error < 1e-6
    assert pl_objective(np.array([1.0, 0.0]), *args)[0] < pl_objective(np.array([-1.0, 0.0]), *args)[0]


def test_pooling_and_train_only_unknown_encoding():
    context = pd.DataFrame(
        {"race_key": ["2022:1", "2023:1"], "season": [2022, 2023], KEY: ["old", "new"], TEAM: ["a", "b"]}
    )
    numeric = pd.DataFrame({"form": [1000.0, 3.0], "absent": [np.nan, np.nan]})
    weights = race_weights(context, {"half_life": 24}, "recent_season_pool")
    assert weights.tolist() == [0.0, 1.0]
    encoder = Encoder.fit(numeric, context, weights)
    assert encoder.medians.tolist() == [3.0, 0.0]
    assert encoder.vocabularies == {KEY: ["new"], TEAM: ["b"]}
    unseen = context.iloc[[0]]
    encoded = encoder.transform(numeric.iloc[[0]], unseen)
    assert encoded[0, -2:].tolist() == [0.0, 0.0]
    np.testing.assert_array_equal(race_weights(context, {"half_life": 24}, "no_recency"), [1.0, 1.0])


@pytest.mark.parametrize("family", STUDY["families"])
def test_model_artifact_roundtrip_and_frozen_fit(frozen, family):
    frames, targets, dataset, splits, config = frozen
    fold, horizon = splits["folds"][0], "post_qualifying"
    train = ordered_block(frames[horizon], fold["train"])
    trial = STUDY["pl_trials"][0] if family == "hierarchical_pl" else STUDY["tree_trials"][0]
    model = fit_model(family, "full", trial, train, targets, dataset, splits, fold, horizon, "train", STUDY, config)
    evaluation = ordered_block(frames[horizon], fold["tune"])
    restored = ForecastModel.restore(json.loads(json.dumps(model.artifact())))
    np.testing.assert_allclose(model.scores(evaluation), restored.scores(evaluation), rtol=0, atol=0)
    assert predictions(model, evaluation, STUDY) == predictions(restored, evaluation, STUDY)
    assert np.std(model.scores(evaluation)) > 0


@pytest.mark.parametrize("block", ["calibration", "evaluation"])
def test_fit_rejects_future_or_calibration(frozen, block):
    frames, targets, dataset, splits, config = frozen
    fold = splits["folds"][0]
    frame = ordered_block(frames["pre_weekend"], fold[block])
    with pytest.raises(ValueError, match="outside"):
        fit_model(
            "hierarchical_pl",
            "full",
            STUDY["pl_trials"][0],
            frame,
            targets,
            dataset,
            splits,
            fold,
            "pre_weekend",
            "train",
            STUDY,
            config,
        )


def test_fit_rejects_changed_feature(frozen):
    frames, targets, dataset, splits, config = frozen
    fold = splits["folds"][0]
    frame = ordered_block(frames["pre_weekend"], fold["train"])
    frame.loc[0, "driver_recency_races"] += 1
    with pytest.raises(ValueError, match="feature values"):
        fit_model(
            "hierarchical_pl",
            "full",
            STUDY["pl_trials"][0],
            frame,
            targets,
            dataset,
            splits,
            fold,
            "pre_weekend",
            "train",
            STUDY,
            config,
        )


def test_no_qualifying_ablation_and_rank_labels(frozen):
    frames, targets, _, splits, _ = frozen
    assert not any("qualifying" in n for n in feature_names("post_qualifying", "no_qualifying", STUDY))
    assert not any("qualifying_position" in n for n in feature_names("pre_weekend", "full", STUDY))
    labels = label_frame(ordered_block(frames["pre_weekend"], splits["folds"][0]["train"]), targets, "rank")
    for _, rows in labels.groupby("race_key"):
        valid = sorted(rows.target.dropna().tolist())
        assert valid == list(range(1, len(valid) + 1))


def test_failed_attempt_retained_before_preparation(tmp_path, monkeypatch):
    def reject():
        raise ValueError("injected lock drift")

    monkeypatch.setattr(cli, "verify_lock", reject)
    with pytest.raises(ValueError, match="injected"):
        cli.run(tmp_path)
    directories = list((tmp_path / "experiments").iterdir())
    assert len(directories) == 1
    assert read_json(directories[0] / "started.json")["status"] == "started"
    assert read_json(directories[0] / "finished.json")["status"] == "failed"


def test_failure_recording_preserves_original(tmp_path, monkeypatch):
    original = cli.write_once

    def write(path, value):
        if path.name == "finished.json":
            raise OSError("injected recording failure")
        original(path, value)

    def reject():
        raise ValueError("original error")

    monkeypatch.setattr(cli, "write_once", write)
    monkeypatch.setattr(cli, "verify_lock", reject)
    with pytest.raises(ValueError, match="original error") as error:
        cli.run(tmp_path)
    assert "Completion recording failed" in error.value.__notes__[0]
    assert list((tmp_path / "experiments").glob("*/started.json"))


def test_benchmark_lock_preserved():
    assert verify_lock()["version"] == "wp06-v2"


def test_retained_reports_and_artifacts_reproduce():
    directories = list((ROOT / "docs/models/wp07/runs/experiments").glob("wp07-*"))
    successes = [d for d in directories if (d / "run-manifest.json").exists()]
    if not successes:
        pytest.skip("committed-source experiment not yet retained")
    hashes = []
    for directory in successes:
        manifest = read_json(directory / "run-manifest.json")
        report = json.loads(gzip.decompress((directory / "report.json.gz").read_bytes()))
        assert digest(report) == manifest["report_sha256"]
        assert report["promotion"]["promoted"] is False
        for horizon in report["horizons"].values():
            for candidate in horizon["candidates"].values():
                assert candidate["calibrated"]["expected_races"] == 70
                assert candidate["calibrated"]["coverage"] == 1
                assert candidate["failures"] == []
                assert len(candidate["races"]) == 70
        hashes.append(manifest["report_sha256"])
    assert len(set(hashes)) == 1


def test_preregistered_study_hash():
    from pipeline.benchmark.artifacts import file_hash

    assert file_hash(cli.CONFIG) == cli.STUDY_HASH


def test_query_groups_reject_interleaved_races():
    with pytest.raises(ValueError, match="query IDs"):
        rank_groups(pd.DataFrame({"race_key": ["r1", "r2", "r1"]}), np.array([1, 1, 2]))


def test_pl_optimizer_failure_is_not_an_artifact(monkeypatch):
    from types import SimpleNamespace

    from pipeline.challengers import models

    context = pd.DataFrame({"race_key": ["r1", "r1"], "season": [2022, 2022], KEY: ["a", "b"], TEAM: ["t", "t"]})
    monkeypatch.setattr(
        models, "minimize", lambda *a, **kw: SimpleNamespace(success=False, message="injected no convergence")
    )
    with pytest.raises(RuntimeError, match="no convergence"):
        ForecastModel.fit(
            "hierarchical_pl",
            pd.DataFrame({"form": [1.0, 2.0]}),
            np.array([1.0, 2.0]),
            context,
            STUDY["pl_trials"][0],
            "full",
            STUDY,
        )
