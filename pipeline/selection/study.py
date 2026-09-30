"""Replay retained contenders under the unchanged WP06 contract, then fail closed."""

from __future__ import annotations

import gzip
import json
from itertools import combinations

from pipeline.benchmark.artifacts import BENCHMARK, CONTRACT, ROOT, digest, file_hash, read_json, verify_lock
from pipeline.benchmark.evaluation import evaluate_predictions
from pipeline.benchmark.metrics import aggregate
from pipeline.benchmark.promotion import comparison_failures, review_gate
from pipeline.benchmark.report import slice_tags
from pipeline.benchmark.uncertainty import assert_paired, uncertainty
from pipeline.challengers.study import label_frame, ordered_block
from pipeline.selection.calibration import fit_winner_calibration
from pipeline.selection.interface import Baseline, Classical, Custom
from pipeline.selection.outputs import Field, coherent_output

DOCS = ROOT / "docs/models/wp09"
WP07 = ROOT / "docs/models/wp07/runs/experiments/wp07-4875d84397424aefb6fea4303b0d394d"
WP08 = ROOT / "docs/research/wp08/runs/wp08-102c448a77374d9f87bc8d0f434f9605"


def zipped(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def verify_sources():
    verify_lock()
    lock = read_json(DOCS / "input-lock.json")
    for name, expected in lock["files"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError(f"WP09 retained input changed: {name}")
    return lock


def field_for(frame):
    from pipeline.benchmark.data import KEY

    return Field(
        frame.race_key.iloc[0],
        frame.horizon.iloc[0],
        frame.cutoff.iloc[0],
        "wp05-frozen-entries-v1",
        tuple(frame[KEY]),
        "exploratory",
        tuple(zip(frame[KEY], frame.constructor_identity_key, strict=True)),
    )


def verify_prediction(actual, recorded):
    if actual["order"] != recorded["order"] or set(actual["winner"]) != set(recorded["winner"]):
        raise ValueError("reloaded prediction order or field drift")
    error = max(abs(p - recorded["winner"][d]) for d, p in actual["winner"].items())
    # Single-race torch matmul can differ from retained batched float32 inference.
    if error > 2e-7:
        raise ValueError(f"reloaded prediction probability drift: {error}")
    return error


def compare(candidate, reference, config):
    assert_paired(reference, candidate)
    a = aggregate(candidate, len(candidate), config["calibration_bins"])
    b = aggregate(reference, len(reference), config["calibration_bins"])
    m, n = a["metrics"], b["metrics"]
    paired = uncertainty(candidate, config, reference)
    tags = sorted({tag for r in candidate for tag in r["slices"]})
    refs = {r["race"]: r for r in reference}
    slices = {}
    for tag in tags:
        rows = [r for r in candidate if tag in r["slices"]]
        delta = uncertainty(rows, config, [refs[r["race"]] for r in rows])
        slices[tag] = {"races": len(rows), "log_loss_regression": -delta["block"]["mean"]}
    comparison = {
        "mean_log_loss_improvement": n["winner_log_loss"] - m["winner_log_loss"],
        "paired_block_ci_lower": paired["block"]["ci95"][0],
        "rank_mae_regression": m["rank_mae"] - n["rank_mae"],
        "rank_correlation_drop": n["rank_correlation"] - m["rank_correlation"],
        "top3_overlap_drop": n["top3_overlap"] - m["top3_overlap"],
        "top10_overlap_drop": n["top10_overlap"] - m["top10_overlap"],
        "winner_hit_drop": n["winner_hit"] - m["winner_hit"],
        "brier_regression": m["winner_brier"] - n["winner_brier"],
        "ece_regression": m["ece"] - n["ece"],
        "ece": m["ece"],
        "coverage": a["coverage"],
        "coverage_drop": b["coverage"] - a["coverage"],
        "all_predeclared_slices_present": bool(tags),
        "slices": slices,
    }
    return {
        "paired": paired,
        "comparison": comparison,
        "diagnostic_guardrail_failures": comparison_failures(comparison, config["promotion"]),
    }


def counted_reliability(outputs, targets, event, bins=10):
    """Supplemental counts preserve WP06 equal-race/1-field weighting.

    Conditional top-k diagnostics use only fully ranked fields; they are not
    estimates of official-event calibration in races with censoring.
    """
    cells = [{"entries": 0, "races": set(), "weight": 0.0, "p": 0.0, "y": 0.0} for _ in range(bins)]
    races = 0
    for key, output in outputs.items():
        field = output["winner"]
        ranks = {r["driver"]: r["rank"] for r in targets[key]}
        if event != "winner" and sorted(r for r in ranks.values() if r is not None) != list(range(1, len(field) + 1)):
            continue
        if 1 not in ranks.values():
            continue
        races += 1
        k = {"winner": 1, "conditional_top3": 3, "conditional_top10": 10}[event]
        for driver, p in output[event].items():
            cell = cells[min(int(p * bins), bins - 1)]
            y = int(ranks[driver] is not None and ranks[driver] <= k)
            cell["entries"] += 1
            cell["races"].add(key)
            cell["weight"] += 1 / len(field)
            cell["p"] += p / len(field)
            cell["y"] += y / len(field)
    return {
        "event": event,
        "eligible_races": races,
        "scheduled_races": len(outputs),
        "scope": "exploratory all entrants" if event == "winner" else "exploratory fully-classified fields only",
        "bins": [
            {
                "lower": i / bins,
                "upper": (i + 1) / bins,
                "entries": c["entries"],
                "races": len(c["races"]),
                "race_weight": c["weight"],
                "mean_probability": c["p"] / c["weight"] if c["weight"] else None,
                "observed_rate": c["y"] / c["weight"] if c["weight"] else None,
            }
            for i, c in enumerate(cells)
        ],
    }


def run_comparison(frames, targets, dataset, splits):
    inputs = verify_sources()
    config = read_json(CONTRACT / "config.json")
    policy = read_json(DOCS / "policy.json")
    old7, old8 = zipped(WP07 / "report.json.gz"), zipped(WP08 / "report.json.gz")
    manifest7 = read_json(WP07 / "run-manifest.json")
    retention8 = read_json(WP08 / "retention.json")
    decisions8 = read_json(WP08 / "selection-frozen.json")["selections"]
    config7 = read_json(ROOT / "docs/models/wp07/config.json")
    config8 = read_json(ROOT / "docs/research/wp08/config.json")
    races = {r["race"]: r for r in dataset["races"]}
    from pipeline.selection.simulation import validation_evidence

    shared_lineage = {
        "dataset_sha256": file_hash(BENCHMARK / "dataset.json"),
        "split_sha256": file_hash(BENCHMARK / "splits.json"),
        "config_sha256": file_hash(CONTRACT / "config.json"),
        "feature_contract_sha256": dataset["feature_contract_sha256"],
        "source_inputs_sha256": digest(inputs),
        "decoder_code_sha256": file_hash(ROOT / "pipeline/selection/outputs.py"),
        "policy_sha256": digest(policy),
        "dependency_lock_sha256": file_hash(ROOT / "uv.lock"),
        "research_dependencies_sha256": file_hash(ROOT / "docs/research/wp08/requirements-macos.txt"),
    }
    output = {
        "simulation_validation": validation_evidence(),
        "protocol": "wp06-v2",
        "inputs_sha256": digest(inputs),
        "policy_sha256": digest(policy),
        "interpretation": "explored reconstruction; not prospective, pristine holdout or as-of evidence",
        "asof": {"eligible_races": 0, "scheduled_races_per_horizon": 70, "metrics": None},
        "prospective": {"races": 0, "blocks": 0, "shadow_races": 0, "metrics": None},
        "incumbent": {"artifact": None, "comparison": None, "reason": "no deployed artifact supplied; unchanged"},
        "horizons": {},
        "calibration_replays": [],
        "artifact_replays": [],
        "upstream_failures": policy["upstream_failures"],
    }
    for horizon, frame in frames.items():
        guesses, raw, sources = {}, {}, {}
        names = list(old7["horizons"][horizon]["candidates"])
        for fold in splits["folds"]:
            adapters = []
            for name in names:
                path = WP07 / "models" / f"{horizon}__{name}__{fold['id']}.json.gz"
                model = Classical(path, manifest7["model_files"][str(path.relative_to(WP07))], horizon)
                recorded = old7["horizons"][horizon]["candidates"][name]["races"]
                adapters.append(
                    (
                        model,
                        recorded,
                        config7["decoder"]["calibration_powers"],
                        model.power,
                        model.artifact["fit_races"],
                    )
                )
            for decision in decisions8:
                if decision["horizon"] != horizon or decision["fold"] != fold["id"]:
                    continue
                path = WP08 / "models" / f"{horizon}-{decision['family']}-{fold['id']}.pt"
                model = Custom(
                    path, retention8["model_aliases"][str(path.relative_to(WP08))]["sha256"], decision, races
                )
                fit_races = fold["train"] + fold["tune"]
                if decision["selected"]["history"] == "last24":
                    fit_races = fit_races[-24:]
                adapters.append(
                    (
                        model,
                        old8["exploratory"][f"{horizon}/{decision['family']}"]["races"],
                        [1 / t for t in config8["calibration_temperatures"]],
                        1 / decision["temperature"],
                        fit_races,
                    )
                )
            for model, recorded, powers, expected_power, fit_races in adapters:
                cal = ordered_block(frame, fold["calibration"])
                predictions = {
                    k: model.raw(rows, field_for(rows))["winner"] for k, rows in cal.groupby("race_key", sort=False)
                }
                card = fit_winner_calibration(
                    predictions,
                    label_frame(cal, targets, "winner"),
                    fit_races=fit_races,
                    fold=fold,
                    dataset=dataset,
                    splits=splits,
                    config=config,
                    powers=powers,
                )
                if card["power"] != expected_power:
                    raise ValueError("retained calibration choice failed held-out replay")
                output["calibration_replays"].append(
                    {"horizon": horizon, "candidate": model.identity, "fold": fold["id"], **card}
                )
                recorded = {r["race"]: r["prediction"] for r in recorded}
                errors = []
                for key in fold["evaluation"]:
                    rows = frame[frame.race_key == key]
                    field = field_for(rows)
                    predicted = model.predict(rows, field)
                    errors.append(verify_prediction(predicted, recorded[key]))
                    guesses.setdefault(model.identity, {})[key] = predicted
                    raw.setdefault(model.identity, {})[key] = model.raw(rows, field)
                    sources[model.identity, key] = model.lineage
                output["artifact_replays"].append(
                    {
                        "horizon": horizon,
                        "candidate": model.identity,
                        "fold": fold["id"],
                        "max_probability_error": max(errors),
                        **model.lineage,
                    }
                )
        for name in config["baselines"][horizon]:
            model = Baseline(
                name,
                horizon,
                {
                    "calibration": "identity; fixed WP06 v2",
                    "model_sha256": inputs["files"]["pipeline/benchmark/baselines.py"],
                },
            )
            for fold in splits["folds"]:
                for key in fold["evaluation"]:
                    rows = frame[frame.race_key == key]
                    guesses.setdefault("baseline:" + name, {})[key] = model.predict(rows, field_for(rows))
                    sources["baseline:" + name, key] = model.lineage
        section = {"retained": "baseline:" + policy["fallbacks"][horizon], "candidates": {}, "pairwise": {}}
        all_records = {}
        for name, predictions in guesses.items():
            result = evaluate_predictions(predictions, targets, dataset, splits, config)
            if result["missing"] or result["summary"]["coverage"] != 1:
                raise ValueError("incomplete scheduled candidate cohort")
            prior_tags = {}
            if name in old7["horizons"][horizon]["candidates"]:
                prior_tags = {r["race"]: r["slices"] for r in old7["horizons"][horizon]["candidates"][name]["races"]}
            outputs = {}
            for row in result["races"]:
                key = row["race"]
                rows = frame[frame.race_key == key]
                row["slices"] = prior_tags.get(key, slice_tags(races[key], rows, targets[key]))
                row["missing_feature_cells"] = int(rows.isna().sum().sum())
                row["prediction"] = predictions[key]
                outputs[key] = coherent_output(
                    field_for(rows),
                    predictions[key],
                    {**shared_lineage, **sources[name, key], "target_sha256": races[key]["target_sha256"]},
                    seed=policy["seed"],
                    per_winner=policy["suffix_samples"],
                )
            result["raw_summary"] = (
                evaluate_predictions(raw[name], targets, dataset, splits, config)["summary"]
                if name in raw
                else result["summary"]
            )
            result["reliability_with_counts"] = {
                event: counted_reliability(outputs, targets, event)
                for event in ("winner", "conditional_top3", "conditional_top10")
            }
            result["coherent_outputs"] = outputs
            all_records[name] = result["races"]
            section["candidates"][name] = result
        baseline = all_records[section["retained"]]
        for name, cell in section["candidates"].items():
            cell["vs_baselines"] = {
                b: compare(all_records[name], all_records["baseline:" + b], config)
                for b in config["baselines"][horizon]
            }
            comparison = compare(all_records[name], baseline, config)
            evidence = {
                "prospective": False,
                "locked_before_outcomes": False,
                "comparators_preregistered": True,
                "identical_cohorts": True,
                "coherent": True,
                "races": 0,
                "blocks": 0,
                "shadow_races": 0,
                "comparisons": {"baseline": comparison["comparison"]},
                "unresolved_failures": True,
            }
            cell["gate_evidence"] = evidence
            cell["review_gate"] = review_gate(evidence, config)
        for a, b in combinations(all_records, 2):
            section["pairwise"][f"{a} minus {b}"] = uncertainty(all_records[b], config, all_records[a])
        section["decision"] = {
            "action": "retain_baseline",
            "selected": section["retained"],
            "promoted": False,
            "reason": (
                "no prospective/as-of evidence, incumbent comparison or operational shadowing; every gate fails closed"
            ),
            "wp07_tune_nominee": old7["selection"]["champions"][horizon],
            "public_publication_authorized": False,
        }
        output["horizons"][horizon] = section
    return output
