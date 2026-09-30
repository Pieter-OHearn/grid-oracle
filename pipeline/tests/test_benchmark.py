"""Acceptance and adversarial regression checks for the preregistered harness."""

from __future__ import annotations

import copy
import math

import pandas as pd
import pytest

from pipeline.benchmark.artifacts import BENCHMARK, CONTRACT, digest, read_json, verify_lock
from pipeline.benchmark.baselines import predict
from pipeline.benchmark.data import KEY, load_dataset
from pipeline.benchmark.fitting import fit_in_block
from pipeline.benchmark.metrics import aggregate, display, score_race
from pipeline.benchmark.promotion import review_gate
from pipeline.benchmark.registry import Registry
from pipeline.benchmark.splits import make_splits, validate_fit_rows, validate_label_availability, validate_splits
from pipeline.benchmark.temporal import TemporalViolation, validate_features
from pipeline.benchmark.uncertainty import assert_paired, uncertainty


@pytest.fixture(scope="module")
def config():
    return read_json(CONTRACT / "config.json")


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    return load_dataset(tmp_path_factory.mktemp("wp06-data"))


@pytest.fixture
def simple_targets():
    return [{"driver": d, "rank": i + 1, "status": "finished", "team": "team"} for i, d in enumerate("abc")]


def test_frozen_inputs_reconstruct(data):
    _, _, dataset = data
    verify_lock()
    assert dataset == read_json(BENCHMARK / "dataset.json")
    assert make_splits(dataset) == read_json(BENCHMARK / "splits.json")
    assert len(dataset["races"]) == 92
    assert dataset["asof_eligible_rows"] == 0


def test_no_fold_splits_race_and_all_blocks_are_chronological(data):
    frames, _, dataset = data
    splits = make_splits(dataset)
    validate_splits(splits, dataset)
    for fold in splits["folds"]:
        for purpose in ("train", "tune", "calibration"):
            frame = frames["pre_weekend"]
            selected = frame[frame.race_key.isin(fold[purpose])]
            ids = list(selected[["race_key", KEY]].itertuples(index=False, name=None))
            validate_fit_rows(ids, fold, dataset, purpose)
            with pytest.raises(ValueError, match="race field"):
                validate_fit_rows(ids[:-1], fold, dataset, purpose)
    assert sum(len(f["evaluation"]) for f in splits["folds"]) == 70
    assert splits["prospective"]["seasons"] == [2027, 2028]
    assert splits["prospective"]["races"] == []


@pytest.mark.parametrize("mutation", ["overlap", "reverse", "unknown", "duplicate", "empty"])
def test_bad_splits_rejected(data, mutation):
    splits = make_splits(data[2])
    fold = splits["folds"][0]
    if mutation == "overlap":
        fold["calibration"][0] = fold["evaluation"][0]
    elif mutation == "reverse":
        fold["train"].reverse()
    elif mutation == "unknown":
        fold["train"][0] = "2099:1"
    elif mutation == "duplicate":
        fold["train"].append(fold["train"][0])
    else:
        fold["train"] = []
    with pytest.raises(ValueError):
        validate_splits(splits, data[2])


@pytest.mark.parametrize(
    "column", ["finish_position", "winner", "qualifying_position", "qualifying_normalized_position"]
)
def test_target_and_qualifying_injection_rejected(data, column):
    frame = data[0]["pre_weekend"].copy()
    frame[column] = 1
    with pytest.raises(TemporalViolation):
        validate_features(frame, "pre_weekend")


def test_pre_weekend_qualifying_missingness_cannot_leak(data):
    frame = data[0]["pre_weekend"].copy()
    frame.loc[0, "missing__qualifying"] = False
    with pytest.raises(TemporalViolation, match="missingness"):
        validate_features(frame, "pre_weekend")


def asof_sample(data):
    frame = data[0]["pre_weekend"].iloc[:1].copy()
    frame["race_key"] = "2027:1"
    frame["season"] = 2027
    frame["asof_eligible"] = True
    frame["entry_provenance"] = "verified_entry_list"
    frame["cutoff"] = "2027-03-01T00:00:00+00:00"
    from pipeline.dataset.historical import FeatureHorizon, FeatureRegistry

    names = [d.name for d in FeatureRegistry.audited_default().enabled_for(FeatureHorizon.PRE_WEEKEND)]
    proof = {
        "first_competitive_session_at": "2027-03-02T00:00:00+00:00",
        "race_start_at": "2027-03-04T00:00:00+00:00",
        "entry_available_at": "2027-02-28T00:00:00+00:00",
        "entry_retrieved_at": "2027-02-28T01:00:00+00:00",
        "features": {
            name: {
                "event_at": "2027-02-20T00:00:00+00:00",
                "available_at": "2027-02-21T00:00:00+00:00",
                "retrieved_at": "2027-02-21T01:00:00+00:00",
            }
            for name in names
        },
    }
    key = f"{frame.iloc[0].race_key}/{frame.iloc[0][KEY]}"
    pinned = {
        "races": [
            {
                "race": "2027:1",
                "drivers": frame[KEY].tolist(),
                "event_at": proof["race_start_at"],
                "first_competitive_session_at": proof["first_competitive_session_at"],
            }
        ]
    }
    return frame, {key: proof}, proof, pinned


@pytest.mark.parametrize("clock", ["available_at", "retrieved_at", "event_at"])
def test_disguised_future_target_fails_temporal_lineage(data, clock):
    frame, evidence, proof, pinned = asof_sample(data)
    validate_features(frame, "pre_weekend", evidence=evidence, dataset=pinned)
    proof["features"]["driver_finish_mean_last_3"][clock] = "2027-03-05T00:00:00+00:00"
    with pytest.raises(TemporalViolation, match="future"):
        validate_features(frame, "pre_weekend", evidence=evidence, dataset=pinned)


def test_archived_flags_cannot_be_upgraded_without_proof(data):
    frame = data[0]["pre_weekend"].copy()
    frame["asof_eligible"] = True
    with pytest.raises(TemporalViolation, match="evidence"):
        validate_features(frame, "pre_weekend", evidence={}, dataset=data[2])


def test_post_qualifying_requires_current_qualifying_and_grid_before_cutoff(data):
    frame, evidence, proof, pinned = asof_sample(data)
    frame["horizon"] = "post_qualifying"
    frame["cutoff"] = "2027-03-03T00:00:00+00:00"
    frame["qualifying_position"] = 1
    frame["qualifying_normalized_position"] = 0.05
    proof["qualifying_final_at"] = "2027-03-02T20:00:00+00:00"
    proof["grid_verified_at"] = "2027-03-02T21:00:00+00:00"
    for name in ("qualifying_position", "qualifying_normalized_position"):
        proof["features"][name] = {k: "2027-03-02T21:00:00+00:00" for k in ("event_at", "available_at", "retrieved_at")}
    validate_features(frame, "post_qualifying", evidence=evidence, dataset=pinned)
    proof["features"]["qualifying_position"]["available_at"] = "2027-03-04T00:00:00+00:00"
    with pytest.raises(TemporalViolation):
        validate_features(frame, "post_qualifying", evidence=evidence, dataset=pinned)


def test_feature_model_rejects_calibration_purpose_for_every_block(data):
    frames, _, dataset = data
    splits = make_splits(dataset)
    fold = splits["folds"][0]
    called = []
    for block in ("train", "tune", "calibration", "evaluation"):
        frame = frames["pre_weekend"]
        frame = frame[frame.race_key.isin(fold[block])]
        labels = frame[["race_key", KEY]].assign(target=1)
        with pytest.raises(ValueError, match="cannot fit calibration"):
            fit_in_block(
                lambda x, y: called.append(True),
                frame,
                labels,
                dataset=dataset,
                splits=splits,
                fold_id=fold["id"],
                purpose="calibration",
                horizon="pre_weekend",
                feature_names=["driver_finish_mean_last_3"],
            )
    assert not called


def test_calibration_labels_must_be_available_before_evaluation():
    with pytest.raises(ValueError, match="unavailable"):
        validate_label_availability(["2027-03-02T00:00:00+00:00"], "2027-03-01T00:00:00+00:00")


def test_hand_computed_metrics(simple_targets, config):
    score = score_race(
        simple_targets, {"order": list("bac"), "winner": {"a": 0.5, "b": 0.25, "c": 0.25}}, list("abc"), config
    )
    assert score["winner_log_loss"] == pytest.approx(math.log(2))
    assert score["winner_brier"] == pytest.approx(0.375)
    assert score["rank_mae"] == pytest.approx(2 / 3)
    assert score["rank_correlation"] == 0.5
    assert score["winner_hit"] == 0
    assert score["top3_overlap"] == 1
    assert aggregate([score], 1, 10)["metrics"]["ece"] == pytest.approx(1 / 3)


def test_ranking_excludes_unclassified_and_normalizes_official_gaps(simple_targets, config):
    simple_targets[1]["rank"] = None
    score = score_race(simple_targets, {"order": list("bac")}, list("abc"), config)
    assert score["rank_mae"] == 0
    assert score["rank_correlation"] == 1
    assert score["top3_overlap"] is None
    assert score["winner_hit"] == 0
    assert score["winner_log_loss"] is None


@pytest.mark.parametrize("p,loss", [(0, -math.log(1e-15)), (1, 0)])
def test_zero_one_numerical_policy(simple_targets, config, p, loss):
    score = score_race(
        simple_targets, {"order": list("abc"), "winner": {"a": p, "b": 1 - p, "c": 0}}, list("abc"), config
    )
    assert score["winner_log_loss"] == pytest.approx(loss)
    assert score["winner_brier"] == (0 if p else 2)


@pytest.mark.parametrize("p", [float("nan"), float("inf"), -1, 1.1, 0.1])
def test_invalid_probability_rejected(simple_targets, config, p):
    with pytest.raises(ValueError, match="incoherent"):
        score_race(simple_targets, {"order": list("abc"), "winner": {"a": p, "b": 0, "c": 0}}, list("abc"), config)


def test_exact_prediction_cohorts_enforced(simple_targets, config):
    with pytest.raises(ValueError, match="cohort"):
        score_race(simple_targets, {"order": list("ab")}, list("abc"), config)
    with pytest.raises(ValueError, match="cohort"):
        score_race(simple_targets, {"order": list("abc"), "winner": {"a": 1}}, list("abc"), config)


def test_missing_evaluation_is_null_and_na(simple_targets, config):
    for row in simple_targets:
        row["rank"] = None
    score = score_race(
        simple_targets, {"order": list("abc"), "winner": dict.fromkeys("abc", 1 / 3)}, list("abc"), config
    )
    summary = aggregate([score], 2, 10)
    assert all(value is None for value in summary["metrics"].values())
    assert summary["coverage"] == 0.5
    assert summary["winner_evaluation_coverage"] == 0
    assert display(None) == "N/A"
    assert display(0) == "0.000000"
    assert aggregate([], 0, 10)["coverage"] is None


def test_paired_block_uncertainty_and_missing_pairs(config):
    reference = [
        {"race": str(i), "fold": str(i // 4), "cohort_sha256": "same", "target_sha256": "same", "winner_log_loss": 2.0}
        for i in range(8)
    ]
    candidate = [{**r, "winner_log_loss": 1.5} for r in reference]
    result = uncertainty(candidate, config, reference)
    assert result["race"]["ci95"] == [0.5, 0.5]
    assert result["block"]["ci95"] == [0.5, 0.5]
    assert result["block"]["units"] == 2
    assert uncertainty(candidate[:1], config)["block"]["ci95"] is None
    candidate[0]["winner_log_loss"] = None
    assert uncertainty(candidate, config, reference)["block"] is None
    candidate[0]["cohort_sha256"] = "different"
    with pytest.raises(ValueError, match="identical"):
        assert_paired(reference, candidate)


def test_baseline_is_entrant_order_invariant(data, config):
    for horizon, names in config["baselines"].items():
        frame = data[0][horizon]
        frame = frame[frame.race_key == "2023:1"]
        for name in names:
            a = predict(frame, name, horizon, config["rank_temperature"])
            b = predict(frame.sample(frac=1, random_state=99), name, horizon, config["rank_temperature"])
            assert a == b
            assert sum(a["winner"].values()) == pytest.approx(1)


def test_registry_preserves_failure_and_never_overwrites(tmp_path):
    registry = Registry(tmp_path)
    first = registry.start({"model": "old"})
    registry.finish(first, error=ValueError("injected future target"))
    second = registry.start({"model": "new"})
    registry.finish(second, result={"loss": 0})
    assert len(registry.records()) == 2
    assert read_json(tmp_path / first / "finished.json")["status"] == "failed"
    assert "not_authorized" in read_json(tmp_path / second / "finished.json")["promotion"]
    with pytest.raises(FileExistsError):
        registry.finish(first, result={"loss": 0})
    assert not hasattr(registry, "promote")


def perfect_gate_evidence():
    comparison = dict.fromkeys(
        (
            "rank_mae_regression",
            "rank_correlation_drop",
            "top3_overlap_drop",
            "top10_overlap_drop",
            "winner_hit_drop",
            "brier_regression",
            "ece_regression",
            "coverage_drop",
        ),
        0.0,
    )
    comparison.update(
        mean_log_loss_improvement=0.02,
        paired_block_ci_lower=0.01,
        coverage=1,
        ece=0.01,
        all_predeclared_slices_present=True,
        slices={"season:2027": {"races": 24, "log_loss_regression": -0.02}},
    )
    return dict(
        prospective=True,
        locked_before_outcomes=True,
        comparators_preregistered=True,
        identical_cohorts=True,
        coherent=True,
        races=48,
        blocks=12,
        shadow_races=6,
        seconds_per_race=0.1,
        peak_rss_mib=100,
        unresolved_failures=False,
        comparisons={"baseline": comparison, "incumbent": copy.deepcopy(comparison)},
    )


def test_even_perfect_or_newest_model_cannot_promote_itself(config):
    evidence = perfect_gate_evidence()
    evidence["created_at"] = "2099-01-01"
    outcome = review_gate(evidence, config)
    assert outcome["eligible_for_independent_review"]
    assert not outcome["promoted"]
    assert not review_gate({"created_at": "2099-01-01"}, config)["eligible_for_independent_review"]


@pytest.mark.parametrize("metric", ["winner_hit_drop", "ece", "coverage", "paired_block_ci_lower", "slices"])
def test_promotion_fails_closed_on_missing_guardrails(config, metric):
    evidence = perfect_gate_evidence()
    del evidence["comparisons"]["baseline"][metric]
    assert not review_gate(evidence, config)["eligible_for_independent_review"]


def test_explored_history_cannot_satisfy_prospective_gate(config):
    evidence = perfect_gate_evidence()
    evidence["prospective"] = False
    assert not review_gate(evidence, config)["eligible_for_independent_review"]


def test_manifest_fingerprint_changes_on_target_mutation(data):
    original = data[2]
    changed = copy.deepcopy(original)
    changed["races"][0]["target_sha256"] = "tampered"
    with pytest.raises(ValueError, match="dataset mismatch"):
        validate_splits(make_splits(original), changed)
    assert digest(original) != digest(changed)


def test_missing_predictions_keep_scheduled_denominator(data, config):
    from pipeline.benchmark.evaluation import evaluate_predictions

    _, targets, dataset = data
    score = evaluate_predictions({}, targets, dataset, make_splits(dataset), config)
    assert score["summary"]["coverage"] == 0
    assert score["summary"]["expected_races"] == 70
    assert score["summary"]["metrics"]["winner_log_loss"] is None
    assert len(score["missing"]) == 70
    assert score["loss_uncertainty"]["block"] is None


def test_evaluation_rejects_changed_labels(data, config):
    from pipeline.benchmark.evaluation import evaluate_predictions

    _, targets, dataset = data
    targets = copy.deepcopy(targets)
    targets["2023:1"][0]["rank"] = 99
    with pytest.raises(ValueError, match="target differs"):
        evaluate_predictions({}, targets, dataset, make_splits(dataset), config)


def test_sliced_blocks_preserve_original_race_block_ids(config):
    from pipeline.benchmark.uncertainty import block_units

    rows = [{"race": str(i), "fold": "2027", "block": f"2027:{i // 4}"} for i in (0, 8, 20)]
    assert block_units(rows, config["block_races"]) == [[0], [1], [2]]


def test_report_is_reproducible_and_separates_audit(data, config):
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from pipeline.benchmark.audit import reproduce_audit
    from pipeline.benchmark.report import build_report, render

    frames, targets, dataset = data
    one = build_report(frames, targets, dataset, make_splits(dataset), config)
    two = build_report(frames, targets, dataset, make_splits(dataset), config)
    assert digest(one) == digest(two)
    assert one["asof"]["metrics"]["winner_log_loss"] is None
    assert one["asof"]["coverage"] == 0
    assert one["prospective"]["coverage"] is None
    assert "**N/A**" in render(one, {})
    for horizon, section in one["exploratory"].items():
        for baseline in section["baselines"].values():
            assert baseline["probabilistic"]["coverage"] == 1
            assert baseline["deterministic"]["metrics"]["winner_log_loss"] is None
            assert baseline["probabilistic"]["metric_race_counts"]["winner_log_loss"] == 70
            assert baseline["probabilistic"]["loss_uncertainty"]["block"]["units"] == 18
            assert any(s.startswith("circuit:") for s in baseline["slices"])
            assert any(s.startswith("driver:") for s in baseline["slices"])
    with TemporaryDirectory() as directory:
        audit = reproduce_audit(Path(directory))
    assert audit["status"] == "reproduced_exactly_except_retrieved_at"


def test_failed_run_keeps_full_provenance_and_failure_event(tmp_path, monkeypatch):
    import pipeline.benchmark.__main__ as cli

    def injected_failure():
        raise ValueError("acceptance injection: locked artifact changed")

    monkeypatch.setattr(cli, "verify_lock", injected_failure)
    with pytest.raises(ValueError, match="acceptance injection"):
        cli.run(tmp_path)
    started = list((tmp_path / "experiments").glob("*/started.json"))
    assert len(started) == 1
    event = read_json(started[0].parent / "prepared.json")
    assert event["code_sha256"]
    assert event["dependency_lock_sha256"]
    assert event["dataset_sha256"]
    assert event["compute"]
    finished = read_json(started[0].parent / "finished.json")
    assert finished["status"] == "failed"
    assert "locked artifact" in finished["error"]


def test_probability_calibrator_rejects_test_probabilities(data):
    from pipeline.benchmark.fitting import fit_calibrator

    _, targets, dataset = data
    splits = make_splits(dataset)
    fold = splits["folds"][0]
    for key, fails in ((fold["evaluation"][0], True), (fold["calibration"][0], False)):
        rows = targets[key]
        probability = {row["driver"]: 1 / len(rows) for row in rows}
        labels = pd.DataFrame([{"race_key": key, KEY: row["driver"], "target": int(row["rank"] == 1)} for row in rows])
        called = []
        kwargs = dict(dataset=dataset, splits=splits, fold_id=fold["id"])
        if fails:
            with pytest.raises(ValueError, match="outside"):
                fit_calibrator(lambda p, y: called.append(y), {key: probability}, labels, **kwargs)
            assert not called
        else:
            fit_calibrator(lambda p, y: called.append(y), {key: probability}, labels, **kwargs)
            assert len(called[0]) == len(rows)
            assert sum(called[0]) == 1


def test_inner_tuning_block_is_scoring_only(data):
    frames, _, dataset = data
    splits = make_splits(dataset)
    fold = splits["folds"][0]
    frame = frames["pre_weekend"]
    frame = frame[frame.race_key.isin(fold["tune"])]
    labels = frame[["race_key", KEY]].assign(target=1)
    with pytest.raises(ValueError, match="scoring-only"):
        fit_in_block(
            lambda x, y: None,
            frame,
            labels,
            dataset=dataset,
            splits=splits,
            fold_id=fold["id"],
            purpose="tune",
            horizon="pre_weekend",
            feature_names=["driver_finish_mean_last_3"],
        )


def test_one_command_repeated_runs_match_and_preserve_events(tmp_path):
    import gzip
    import json

    from pipeline.benchmark.__main__ import run

    first = run(tmp_path)
    second = run(tmp_path)
    manifests = []
    for identifier in (first, second):
        directory = tmp_path / "experiments" / identifier
        report = json.loads(gzip.decompress((directory / "report.json.gz").read_bytes()))
        manifest = read_json(directory / "run-manifest.json")
        assert digest(report) == manifest["report_sha256"]
        assert read_json(directory / "finished.json")["status"] == "succeeded"
        assert "**N/A**" in (directory / "report.md").read_text()
        manifests.append(manifest)
    assert first != second
    assert manifests[0]["report_sha256"] == manifests[1]["report_sha256"]
    assert manifests[0]["code_sha256"] == manifests[1]["code_sha256"]
