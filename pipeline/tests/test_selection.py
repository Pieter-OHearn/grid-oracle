"""WP09 probability, information boundary, registry and WP03 integration checks."""

from copy import deepcopy
from dataclasses import replace
from itertools import permutations

import numpy as np
import pytest

from pipeline.benchmark.artifacts import CONTRACT, digest, read_json
from pipeline.challengers.study import label_frame, ordered_block
from pipeline.selection.calibration import fit_winner_calibration
from pipeline.selection.interface import Baseline, Classical, check_frame
from pipeline.selection.ledger import Ledger
from pipeline.selection.outputs import Field, coherent_output, joint_distribution, validate_output
from pipeline.selection.storage import store_research_output
from pipeline.selection.study import WP07, counted_reliability, field_for, verify_sources
from pipeline.tests.test_challengers import frozen as upstream_frozen
from pipeline.tests.test_provenance import NOW, _run
from pipeline.tests.test_provenance import provenance as upstream_provenance

frozen = upstream_frozen
provenance = upstream_provenance


def example(n=4, probability=None):
    ids = tuple(f"entry:{i:02d}" for i in range(n))
    field = Field("2026:7", "pre_weekend", "2026-05-01T09:50:00+00:00", "entries-v1", ids)
    p = np.full(n, 1 / n) if probability is None else np.asarray(probability, dtype=float)
    return field, {"order": list(ids), "winner": dict(zip(ids, p.tolist(), strict=True))}


@pytest.mark.parametrize("n", [1, 2, 3, 20, 22])
def test_joint_draws_are_permutations_and_marginals_coherent(n):
    field, p = example(n)
    joint = joint_distribution(field, p, seed=7, per_winner=128)
    assert np.all(np.sort(joint["draws"], axis=1) == np.arange(n))
    np.testing.assert_allclose(joint["matrix"].sum(axis=0), 1, atol=1e-12)
    np.testing.assert_allclose(joint["matrix"].sum(axis=1), 1, atol=1e-12)
    assert joint["weights"].sum() == pytest.approx(1)
    output = coherent_output(field, p, {}, seed=7, per_winner=128)
    validate_output(output, field)
    for e in field.entries:
        assert 0 <= output["conditional_top3"][e] <= 1
        assert 0 <= output["conditional_top10"][e] <= 1
        assert output["winner"][e] <= output["conditional_top3"][e] + 1e-12
        assert output["conditional_top3"][e] <= output["conditional_top10"][e] + 1e-12
    assert sum(output["conditional_top3"].values()) == pytest.approx(min(3, n))
    assert sum(output["conditional_top10"].values()) == pytest.approx(min(10, n))


@pytest.mark.parametrize(
    "probability", [[1, 0, 0], [0, 0.4, 0.6], [1e-300, 0.4, 0.6], [0.999999, 0.0000005, 0.0000005]]
)
def test_degenerate_and_extreme_probabilities(probability):
    field, p = example(3, probability)
    output = coherent_output(field, p, {}, seed=19)
    assert output["winner"] == p["winner"]
    validate_output(output, field)


@pytest.mark.parametrize(
    "probability", [[float("nan"), 0.2, 0.8], [float("inf"), 0, 0], [-0.1, 0.5, 0.6], [1.1, 0, 0], [0.2, 0.2, 0.2]]
)
def test_invalid_probabilities_fail_without_silent_repair(probability):
    field, p = example(3, probability)
    with pytest.raises(ValueError):
        coherent_output(field, p, {})


def test_exact_small_pl_and_sampling_convergence():
    field, p = example(3, [0.5, 0.3, 0.2])
    exact = np.zeros((3, 3))
    weights = np.array(list(p["winner"].values()))
    for order in permutations(range(3)):
        mass = 1.0
        remaining = list(range(3))
        for i in order:
            mass *= weights[i] / sum(weights[remaining])
            remaining.remove(i)
        for rank, i in enumerate(order):
            exact[i, rank] += mass
    # Across independent fixed seeds, larger samples reduce total squared error.
    errors = []
    for count in (64, 4096):
        matrices = [joint_distribution(field, p, seed=s, per_winner=count)["matrix"] for s in range(12)]
        errors.append(np.mean([np.square(a - exact).sum() for a in matrices]))
    assert errors[1] < errors[0] / 8
    np.testing.assert_allclose(matrices[-1], exact, atol=0.02)


def test_correlated_outcomes_and_no_independent_bernoulli_field():
    field, p = example(6)
    sample = joint_distribution(field, p, seed=41, per_winner=1024)
    draws, w = sample["draws"], sample["weights"]
    wins = np.stack([draws[:, 0] == i for i in range(6)], axis=1)
    podium = np.stack([(draws[:, :3] == i).any(axis=1) for i in range(6)], axis=1)
    assert np.all(wins.sum(axis=1) == 1)
    assert np.all(podium.sum(axis=1) == 3)
    assert np.dot(w, wins[:, 0] & wins[:, 1]) == 0
    covariance = np.dot(w, podium[:, 0] & podium[:, 1]) - np.dot(w, podium[:, 0]) * np.dot(w, podium[:, 1])
    assert covariance == pytest.approx(-0.05, abs=0.015)


def test_reproducibility_entry_order_and_revision_protection():
    field, p = example(4, [0.4, 0.3, 0.2, 0.1])
    output = coherent_output(field, p, {"artifact": "test"}, seed=6)
    shuffled = replace(field, entries=field.entries[::-1])
    assert coherent_output(shuffled, p, {"artifact": "test"}, seed=6) == output
    for changed in (
        replace(field, revision="v2"),
        replace(field, entries=field.entries[:-1]),
        replace(field, horizon="post_qualifying"),
        replace(field, cutoff="2026-05-02T09:50:00+00:00"),
    ):
        with pytest.raises(ValueError, match="revision"):
            validate_output(output, changed)
    with pytest.raises(ValueError):
        Field("r", "pre_weekend", "before_first_competitive_session", "v1", ("a",))
    bad = deepcopy(output)
    bad["conditional_top3"][field.entries[0]] = 0
    with pytest.raises(ValueError, match="nested"):
        validate_output(bad, field)
    bad = deepcopy(output)
    bad["official_top3"] = {"a": 1}
    with pytest.raises(ValueError, match="unsupported"):
        validate_output(bad, field)


def calibration_case(frozen):
    frames, targets, dataset, splits, config = frozen
    fold = splits["folds"][0]
    frame = ordered_block(frames["pre_weekend"], fold["calibration"])
    model = Baseline("standings", "pre_weekend", {})
    predictions = {
        key: model.predict(rows, field_for(rows))["winner"] for key, rows in frame.groupby("race_key", sort=False)
    }
    kwargs = dict(
        fit_races=fold["train"] + fold["tune"],
        fold=fold,
        dataset=dataset,
        splits=splits,
        config=config,
        powers=[0.5, 1, 2],
    )
    return predictions, label_frame(frame, targets, "winner"), kwargs


def test_calibration_only_on_complete_prior_heldout_races(frozen):
    predictions, labels, kwargs = calibration_case(frozen)
    fitted = fit_winner_calibration(predictions, labels, **kwargs)
    assert fitted["out_of_sample"] and not fitted["asof_eligible"]
    assert fitted["predictions_sha256"] == digest(predictions)
    with pytest.raises(ValueError, match="overlap"):
        fit_winner_calibration(predictions, labels, **{**kwargs, "fit_races": kwargs["fold"]["calibration"]})
    with pytest.raises(ValueError, match="outside"):
        fit_winner_calibration(predictions, labels, **{**kwargs, "fit_races": kwargs["fold"]["evaluation"]})
    missing = deepcopy(predictions)
    missing.pop(next(iter(missing)))
    with pytest.raises(ValueError):
        fit_winner_calibration(missing, labels, **kwargs)
    labels["available_at"] = "2099-01-01T00:00:00+00:00"
    with pytest.raises(ValueError):
        fit_winner_calibration(predictions, labels, **kwargs)


def test_calibration_rejects_target_corruption_and_outer_rows(frozen):
    predictions, labels, kwargs = calibration_case(frozen)
    labels.loc[labels.target == 1, "target"] = 0
    with pytest.raises(ValueError, match="label differs"):
        fit_winner_calibration(predictions, labels, **kwargs)
    predictions[kwargs["fold"]["evaluation"][0]] = predictions.pop(next(iter(predictions)))
    with pytest.raises(ValueError):
        fit_winner_calibration(predictions, labels, **kwargs)


def test_adapter_identity_cutoff_and_artifact_hash(frozen):
    frames, _, _, splits, _ = frozen
    rows = ordered_block(frames["pre_weekend"], [splits["folds"][0]["evaluation"][0]])
    field = field_for(rows)
    check_frame(rows, field, "pre_weekend")
    with pytest.raises(ValueError):
        check_frame(rows, replace(field, revision="v2", entries=field.entries[:-1]), "pre_weekend")
    with pytest.raises(ValueError):
        check_frame(rows, field, "post_qualifying")
    transferred = rows.copy()
    transferred.loc[transferred.index[0], "constructor_identity_key"] = "new-team"
    with pytest.raises(ValueError, match="constructor"):
        check_frame(transferred, field, "pre_weekend")
    corrupt = rows.copy()
    corrupt["target"] = 1
    with pytest.raises(ValueError):
        check_frame(corrupt, field, "pre_weekend")
    path = WP07 / "models/pre_weekend__xgb_regression__full__2023.json.gz"
    with pytest.raises(ValueError, match="checksum"):
        Classical(path, "0" * 64, "pre_weekend")


def descriptor(identity="baseline", horizon="pre_weekend", author="owner"):
    return {
        "identity": identity,
        "horizon": horizon,
        "author": author,
        "baseline": "standings",
        "lineage": {
            k: "a" * 64
            for k in ("model_sha256", "calibrator_sha256", "config_sha256", "dataset_sha256", "split_sha256")
        },
    }


def passing_evidence():
    # Synthetic unit fixture only; never retained as prospective evidence.
    comparison = {
        "mean_log_loss_improvement": 0.1,
        "paired_block_ci_lower": 0.01,
        "coverage": 1,
        "all_predeclared_slices_present": True,
        "slices": {"all": {"races": 40, "log_loss_regression": -0.1}},
    }
    for key in (
        "rank_mae_regression",
        "rank_correlation_drop",
        "top3_overlap_drop",
        "top10_overlap_drop",
        "winner_hit_drop",
        "brier_regression",
        "ece_regression",
        "ece",
        "coverage_drop",
    ):
        comparison[key] = 0
    return {
        "prospective": True,
        "locked_before_outcomes": True,
        "comparators_preregistered": True,
        "identical_cohorts": True,
        "coherent": True,
        "races": 40,
        "blocks": 10,
        "shadow_races": 6,
        "seconds_per_race": 0.1,
        "peak_rss_mib": 100,
        "unresolved_failures": False,
        "comparisons": {"baseline": comparison, "incumbent": comparison},
    }


def test_ledger_requires_review_and_explicit_promotion_then_rollback(tmp_path):
    ledger = Ledger(tmp_path / "ledger")
    head = ledger.append("bootstrap", descriptor(), actor="owner", reason="fixed fallback", expected_head=None)
    head = ledger.append(
        "register",
        descriptor("model", author="researcher"),
        actor="researcher",
        reason="experiment",
        expected_head=head,
    )
    assert ledger.snapshot()["active"] == {"pre_weekend": "baseline"}
    head = ledger.append(
        "challenge", {"identity": "model"}, actor="researcher", reason="propose review", expected_head=head
    )
    with pytest.raises(ValueError, match="approved"):
        ledger.append("promote", {"identity": "model"}, actor="owner", reason="premature", expected_head=head)
    binding = {k: descriptor("model", author="researcher")[k] for k in ("identity", "horizon", "lineage")}
    approval = {
        "identity": "model",
        "binding_sha256": digest(binding),
        "incumbent": "baseline",
        "baseline": "standings",
        "review_reference": "unit-fixture-review",
        "evidence": passing_evidence(),
    }
    with pytest.raises(ValueError, match="independent"):
        ledger.append("approve", approval, actor="researcher", reason="self-review", expected_head=head)
    failed = deepcopy(approval)
    failed["evidence"]["prospective"] = False
    with pytest.raises(ValueError, match="gate failed"):
        ledger.append("approve", failed, actor="reviewer", reason="reject history", expected_head=head)
    head = ledger.append("approve", approval, actor="reviewer", reason="synthetic acceptance", expected_head=head)
    assert ledger.snapshot()["active"]["pre_weekend"] == "baseline"
    head = ledger.append("promote", {"identity": "model"}, actor="owner", reason="manual action", expected_head=head)
    assert ledger.snapshot()["models"]["baseline"]["state"] == "retired"
    previous = ledger.events()
    head = ledger.append(
        "rollback", {"identity": "baseline"}, actor="owner", reason="manual rollback", expected_head=head
    )
    assert ledger.snapshot()["active"]["pre_weekend"] == "baseline"
    assert ledger.events()[:-1] == previous
    with pytest.raises(ValueError, match="stale"):
        ledger.append("register", descriptor("late"), actor="owner", reason="race", expected_head=None)
    (ledger.root / "000000.json").write_text("{}")
    with pytest.raises((ValueError, KeyError)):
        ledger.snapshot()


def test_ledger_rejects_cross_horizon_and_unreviewed_rollback(tmp_path):
    ledger = Ledger(tmp_path)
    with pytest.raises(ValueError):
        ledger.append(
            "bootstrap",
            descriptor(horizon="post_qualifying"),
            actor="owner",
            reason="wrong fallback",
            expected_head=None,
        )
    head = ledger.append("register", descriptor("new"), actor="owner", reason="register", expected_head=None)
    with pytest.raises(ValueError, match="prior champion"):
        ledger.append("rollback", {"identity": "new"}, actor="owner", reason="invalid", expected_head=head)


def test_counted_reliability_excludes_censored_conditional_targets():
    field, p = example(4)
    output = coherent_output(field, p, {})
    targets = {
        "full": [{"driver": e, "rank": i + 1} for i, e in enumerate(field.entries)],
        "censored": [{"driver": e, "rank": i + 1 if i < 3 else None} for i, e in enumerate(field.entries)],
    }
    outputs = {k: output for k in targets}
    winner = counted_reliability(outputs, targets, "winner")
    conditional = counted_reliability(outputs, targets, "conditional_top3")
    assert winner["eligible_races"] == 2
    assert conditional["eligible_races"] == 1
    assert sum(b["entries"] for b in winner["bins"]) == 8
    assert sum(b["entries"] for b in conditional["bins"]) == 4


def test_wp03_research_storage_is_reproducible_immutable_and_cannot_publish(provenance):
    from gridoracle.provenance.store import ProvenanceError

    store, _, _ = provenance
    field, p = example(2, [0.6, 0.4])
    output = coherent_output(field, p, {"model_sha256": "a" * 64})
    run = replace(_run(key="wp09-research"), input_manifest={"race_key": field.race})
    identifier = store_research_output(store, run, output, field)
    assert store_research_output(store, run, output, field) == identifier
    with pytest.raises(ProvenanceError, match="legacy_unverified"):
        store.publish(identifier, published_at=NOW)
    changed = replace(field, revision="v2")
    revised = coherent_output(changed, p, {"model_sha256": "a" * 64})
    with pytest.raises(ProvenanceError):
        store_research_output(store, run, revised, changed)
    assert (
        store_research_output(store, replace(run, idempotency_key="wp09-research-v2"), revised, changed) != identifier
    )


def test_locks_and_retained_source_integrity():
    assert verify_sources()["version"] == "wp09-retained-inputs-v1"
    assert read_json(CONTRACT / "config.json")["promotion"]["min_races"] == 40


@pytest.mark.parametrize(
    "key,value", [("target", "official_classification"), ("publication_eligible", True), ("schema", "unrecognized")]
)
def test_rejects_false_publication_and_target_claims(key, value):
    field, prediction = example()
    output = coherent_output(field, prediction, {})
    output[key] = value
    with pytest.raises(ValueError, match="unapproved"):
        validate_output(output, field)


def test_review_cannot_invent_a_missing_incumbent(tmp_path):
    ledger = Ledger(tmp_path)
    head = ledger.append("register", descriptor("new"), actor="owner", reason="candidate", expected_head=None)
    head = ledger.append("challenge", {"identity": "new"}, actor="owner", reason="request review", expected_head=head)
    with pytest.raises(ValueError, match="current incumbent"):
        ledger.append("approve", {"identity": "new"}, actor="reviewer", reason="no incumbent", expected_head=head)
