"""Frozen-cohort fit, tune, refit and calibration phases for WP07."""

from __future__ import annotations

import gzip
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.benchmark.artifacts import canonical, digest, write_bytes_once, write_once
from pipeline.benchmark.baselines import predict as baseline_predict
from pipeline.benchmark.contracts import verify_feature_values, verify_inputs
from pipeline.benchmark.data import KEY
from pipeline.benchmark.evaluation import evaluate_predictions
from pipeline.benchmark.fitting import fit_calibrator, fit_in_block
from pipeline.benchmark.metrics import score_race
from pipeline.benchmark.promotion import comparison_failures, review_gate
from pipeline.benchmark.report import deterministic_summary, slice_report, slice_tags, summarize
from pipeline.benchmark.uncertainty import uncertainty
from pipeline.challengers.decoder import calibrate, choose_power, decode
from pipeline.challengers.models import TEAM, ForecastModel
from pipeline.dataset.historical import FeatureHorizon, FeatureRegistry


def feature_names(horizon: str, variant: str, study: dict) -> list[str]:
    names = [d.name for d in FeatureRegistry.audited_default().enabled_for(FeatureHorizon(horizon))]
    if variant == "no_recency":
        names = [n for n in names if n not in study["recency_removed"]]
    if variant == "no_qualifying":
        names = [n for n in names if "qualifying" not in n]
    return names


def label_frame(context: pd.DataFrame, targets: dict, kind: str) -> pd.DataFrame:
    mapping = {}
    for race in context.race_key.unique():
        classified = sorted((r for r in targets[race] if r["rank"] is not None), key=lambda r: r["rank"])
        if not classified or classified[0]["rank"] != 1:
            raise ValueError("missing fitting winner")
        ranks = {r["driver"]: i + 1 for i, r in enumerate(classified)}
        for row in targets[race]:
            mapping[race, row["driver"]] = (
                int(row["driver"] == classified[0]["driver"]) if kind == "winner" else ranks.get(row["driver"])
            )
    result = context[["race_key", KEY]].copy()
    result["target"] = [mapping[race, driver] for race, driver in result.itertuples(index=False, name=None)]
    return result


def ordered_block(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    parts = [frame[frame.race_key == key].sort_values(KEY) for key in keys]
    return pd.concat(parts, ignore_index=True)


def predictions(model: ForecastModel, frame: pd.DataFrame, study: dict) -> dict:
    return {
        race: decode(rows[KEY].tolist(), model.scores(rows), study["decoder"]["initial_temperature"])
        for race, rows in frame.groupby("race_key", sort=False)
    }


def tune_loss(outputs: dict, targets: dict, dataset: dict, config: dict) -> float:
    fields = {r["race"]: r["drivers"] for r in dataset["races"]}
    losses = [score_race(targets[key], p, fields[key], config)["winner_log_loss"] for key, p in outputs.items()]
    if not losses or any(loss is None for loss in losses):
        raise ValueError("incomplete tuning score")
    return float(np.mean(losses))


def fit_model(
    family: str,
    variant: str,
    trial: dict,
    frame: pd.DataFrame,
    targets: dict,
    dataset: dict,
    splits: dict,
    fold: dict,
    horizon: str,
    purpose: str,
    study: dict,
    config: dict,
):
    return fit_in_block(
        lambda numeric, labels: ForecastModel.fit(family, numeric, labels, frame, trial, variant, study),
        frame,
        label_frame(frame, targets, "rank"),
        dataset=dataset,
        splits=splits,
        fold_id=fold["id"],
        purpose=purpose,
        horizon=horizon,
        feature_names=feature_names(horizon, variant, study),
        config=config,
        target_kind="rank",
    )


def prepare_candidates(
    frames: dict, targets: dict, dataset: dict, splits: dict, config: dict, study: dict, directory: Path
) -> tuple[list[dict], dict, dict]:
    """Complete every selection/artifact before reading outer outcomes."""
    verify_inputs(dataset, splits, config)
    prepared, costs, inner = [], {}, {}
    for horizon, frame in frames.items():
        verify_feature_values(frame, horizon, dataset)
        variants = [v for v in study["variants"] if v != "no_qualifying" or horizon == "post_qualifying"]
        for family in study["families"]:
            trials = study["pl_trials"] if family == "hierarchical_pl" else study["tree_trials"]
            for variant in variants:
                name = f"{family}__{variant}"
                for fold in splits["folds"]:
                    identifier = f"{horizon}__{name}__{fold['id']}"
                    train = ordered_block(frame, fold["train"])
                    tune = ordered_block(frame, fold["tune"])
                    trial_results = []
                    for index, trial in enumerate(trials):
                        started = time.perf_counter()
                        event = {
                            "candidate": identifier,
                            "trial_index": index,
                            "config": trial,
                            "fit_rows_sha256": digest(train[["race_key", KEY]].values.tolist()),
                            "tune_races": fold["tune"],
                        }
                        try:
                            model = fit_model(
                                family,
                                variant,
                                trial,
                                train,
                                targets,
                                dataset,
                                splits,
                                fold,
                                horizon,
                                "train",
                                study,
                                config,
                            )
                            outputs = predictions(model, tune, study)
                            loss = tune_loss(outputs, targets, dataset, config)
                            event.update(
                                status="succeeded",
                                winner_log_loss=loss,
                                optimization=model.optimization,
                                predictions_sha256=digest(outputs),
                            )
                        except (ValueError, RuntimeError) as error:
                            event.update(
                                status="failed", winner_log_loss=None, error=f"{type(error).__name__}: {error}"
                            )
                        elapsed = time.perf_counter() - started
                        write_once(directory / "trials" / f"{identifier}__{index}.json", {**event, "seconds": elapsed})
                        costs[f"{identifier}__trial{index}"] = {"seconds": elapsed, "status": event["status"]}
                        trial_results.append(event)
                    successful = [e for e in trial_results if e["status"] == "succeeded"]
                    if not successful:
                        raise RuntimeError(f"all trials failed for {identifier}")
                    chosen = min(successful, key=lambda e: (e["winner_log_loss"], e["trial_index"]))
                    inner.setdefault(horizon, {}).setdefault(name, []).append(chosen["winner_log_loss"])
                    refit = ordered_block(frame, fold["train"] + fold["tune"])
                    started = time.perf_counter()
                    model = fit_model(
                        family,
                        variant,
                        chosen["config"],
                        refit,
                        targets,
                        dataset,
                        splits,
                        fold,
                        horizon,
                        "refit",
                        study,
                        config,
                    )
                    calibration = ordered_block(frame, fold["calibration"])
                    base = predictions(model, calibration, study)
                    sizes = [len(p["winner"]) for p in base.values()]
                    decoder = fit_calibrator(
                        lambda p, y: choose_power(p, y, sizes, study["decoder"]["calibration_powers"]),
                        {r: p["winner"] for r, p in base.items()},
                        label_frame(calibration, targets, "winner"),
                        dataset=dataset,
                        splits=splits,
                        fold_id=fold["id"],
                        config=config,
                    )
                    artifact = {
                        "candidate": identifier,
                        "selected_config": chosen["config"],
                        "fit_races": fold["train"] + fold["tune"],
                        "calibration_races": fold["calibration"],
                        "fit_rows_sha256": digest(refit[["race_key", KEY]].values.tolist()),
                        "model": model.artifact(),
                        "decoder": decoder,
                        "study_sha256": digest(study),
                    }
                    artifact_hash = digest(artifact)
                    write_bytes_once(
                        directory / "models" / f"{identifier}.json.gz", gzip.compress(canonical(artifact), mtime=0)
                    )
                    costs[identifier] = {"refit_and_calibration_seconds": time.perf_counter() - started}
                    prepared.append(
                        {
                            "identifier": identifier,
                            "name": name,
                            "family": family,
                            "variant": variant,
                            "horizon": horizon,
                            "fold": fold,
                            "model": model,
                            "decoder": decoder,
                            "trials": trial_results,
                            "artifact_sha256": artifact_hash,
                            "refit_frame": refit,
                        }
                    )
                    print(f"Prepared {identifier}", flush=True)
    champions = {
        h: min(study["families"], key=lambda f: (np.mean(names[f"{f}__full"]), study["families"].index(f)))
        for h, names in inner.items()
    }
    selection = {"champions": champions, "inner_losses": inner, "rule": study["selection"]}
    write_once(directory / "selection.json", selection)
    return prepared, costs, selection


def failure_tags(frame: pd.DataFrame, refit: pd.DataFrame, dataset: dict, fold: dict, study: dict) -> dict:
    """Entrant slices use entry metadata/history, never current outcome labels."""
    seen = set(refit[KEY])
    counts = refit.groupby(KEY).race_key.nunique()
    previous_team, changes = {}, {}
    for race in dataset["races"]:
        rows = frame[frame.race_key == race["race"]]
        changed = []
        for row in rows.to_dict("records"):
            driver, team = row[KEY], row[TEAM]
            if driver in previous_team and previous_team[driver] != team:
                changed.append(driver)
            previous_team[driver] = team
        changes[race["race"]] = changed
    result = {}
    for key in fold["evaluation"]:
        rows = frame[frame.race_key == key]
        cold = sorted(set(rows[KEY]) - seen)
        rare = sorted(d for d in rows[KEY] if counts.get(d, 0) <= study["slices"]["rare_entry_max_train_races"])
        low = sorted(rows.loc[rows.driver_recency_races <= study["slices"]["low_experience_max_prior_races"], KEY])
        tags = [
            f"cold_start:{bool(cold)}",
            f"low_experience:{bool(low)}",
            f"rare_entry:{bool(rare)}",
            f"team_change:{bool(changes[key])}",
            f"recent_drift:{key in fold['evaluation'][-study['slices']['recent_drift_last_races'] :]}",
        ]
        result[key] = {
            "tags": tags,
            "cold_drivers": cold,
            "rare_entry_drivers": rare,
            "low_experience_drivers": low,
            "team_changed_drivers": changes[key],
        }
    return result


def evaluate_candidates(
    prepared: list[dict],
    frames: dict,
    targets: dict,
    dataset: dict,
    splits: dict,
    config: dict,
    study: dict,
    costs: dict,
    selection: dict,
) -> dict:
    expected = sum(len(f["evaluation"]) for f in splits["folds"])
    races = {r["race"]: r for r in dataset["races"]}
    grouped = {}
    for item in prepared:
        horizon, fold = item["horizon"], item["fold"]
        group = grouped.setdefault(
            (horizon, item["name"]), {"raw": {}, "calibrated": {}, "annotations": {}, "fits": []}
        )
        evaluation = ordered_block(frames[horizon], fold["evaluation"])
        started = time.perf_counter()
        raw = predictions(item["model"], evaluation, study)
        outputs = {key: calibrate(p, item["decoder"]["power"]) for key, p in raw.items()}
        costs[item["identifier"]]["inference_seconds_per_race"] = (time.perf_counter() - started) / len(raw)
        tags = failure_tags(frames[horizon], item["refit_frame"], dataset, fold, study)
        group["raw"].update(raw)
        group["calibrated"].update(outputs)
        group["fits"].append({k: item[k] for k in ("identifier", "artifact_sha256", "decoder", "trials")})
        for key in fold["evaluation"]:
            rows = evaluation[evaluation.race_key == key]
            group["annotations"][key] = {
                "slices": slice_tags(races[key], rows, targets[key]) + tags[key]["tags"],
                "failure_context": {k: v for k, v in tags[key].items() if k != "tags"},
                "missing_feature_cells": int(rows[feature_names(horizon, "full", study)].isna().sum().sum()),
                "prediction": outputs[key],
            }
    report = {
        "protocol": config["protocol_version"],
        "study": study["study"],
        "selection": selection,
        "interpretation": "explored reconstruction only; no future superiority or promotion claims",
        "asof": {"eligible_races": 0, "expected_races": expected, "metrics": None},
        "prospective": {"status": splits["prospective"]["status"], "metrics": None},
        "promotion": {
            "promoted": False,
            "reason": "No prospective evidence, incumbent or shadowing; WP09 review required",
        },
        "unavailable_ablations": study["unavailable_ablations"],
        "horizons": {},
    }
    for horizon in frames:
        baseline_cells, baseline_records = {}, {}
        for name in config["baselines"][horizon]:
            output = {
                key: baseline_predict(
                    frames[horizon][frames[horizon].race_key == key], name, horizon, config["rank_temperature"]
                )
                for fold in splits["folds"]
                for key in fold["evaluation"]
            }
            records = evaluate_predictions(output, targets, dataset, splits, config)["races"]
            records = [
                {
                    **r,
                    "missing_feature_cells": int(
                        frames[horizon]
                        .loc[frames[horizon].race_key == r["race"], feature_names(horizon, "full", study)]
                        .isna()
                        .sum()
                        .sum()
                    ),
                }
                for r in records
            ]
            baseline_records[name] = records
            baseline_cells[name] = summarize(records, expected, config)
        section = {"baselines": baseline_cells, "comparator": study["comparators"][horizon], "candidates": {}}
        for (h, name), group in grouped.items():
            if h != horizon:
                continue
            result = evaluate_predictions(group["calibrated"], targets, dataset, splits, config)
            records = [{**r, **group["annotations"][r["race"]]} for r in result["races"]]
            raw = evaluate_predictions(group["raw"], targets, dataset, splits, config)
            reference = baseline_records[section["comparator"]]
            section["candidates"][name] = {
                "input_fingerprints": result["input_fingerprints"],
                "calibrated": summarize(records, expected, config),
                "uncalibrated": raw["summary"],
                "deterministic": deterministic_summary(records, expected, config),
                "paired_vs_comparator": uncertainty(records, config, reference),
                "paired_vs_baselines": {b: uncertainty(records, config, rows) for b, rows in baseline_records.items()},
                "folds": {
                    f["id"]: summarize([r for r in records if r["fold"] == f["id"]], len(f["evaluation"]), config)
                    for f in splits["folds"]
                },
                "slices": slice_report(records, config),
                "races": records,
                "fits": group["fits"],
                "failures": result["missing"],
            }
        for name, cell in section["candidates"].items():
            family = name.split("__")[0]
            full = section["candidates"][f"{family}__full"]["races"]
            cell["paired_vs_full"] = uncertainty(cell["races"], config, full)
            cell["slice_vs_comparator"] = {
                tag: uncertainty(
                    [r for r in cell["races"] if tag in r["slices"]],
                    config,
                    [r for r in reference if r["race"] in {s["race"] for s in cell["races"] if tag in s["slices"]}],
                )
                for tag in cell["slices"]
            }
            summary = cell["calibrated"]
            candidate_m = summary["metrics"]
            baseline = section["baselines"][section["comparator"]]
            baseline_m = baseline["metrics"]
            paired = cell["paired_vs_comparator"]["block"]
            comparison = {
                "mean_log_loss_improvement": baseline_m["winner_log_loss"] - candidate_m["winner_log_loss"],
                "paired_block_ci_lower": paired["ci95"][0],
                "rank_mae_regression": candidate_m["rank_mae"] - baseline_m["rank_mae"],
                "rank_correlation_drop": baseline_m["rank_correlation"] - candidate_m["rank_correlation"],
                "top3_overlap_drop": baseline_m["top3_overlap"] - candidate_m["top3_overlap"],
                "top10_overlap_drop": baseline_m["top10_overlap"] - candidate_m["top10_overlap"],
                "winner_hit_drop": baseline_m["winner_hit"] - candidate_m["winner_hit"],
                "brier_regression": candidate_m["winner_brier"] - baseline_m["winner_brier"],
                "ece_regression": candidate_m["ece"] - baseline_m["ece"],
                "ece": candidate_m["ece"],
                "coverage": summary["coverage"],
                "coverage_drop": baseline["coverage"] - summary["coverage"],
                "all_predeclared_slices_present": True,
                "slices": {
                    tag: {
                        "races": subset["expected_races"],
                        "log_loss_regression": -cell["slice_vs_comparator"][tag]["block"]["mean"],
                    }
                    for tag, subset in cell["slices"].items()
                },
            }
            cell["diagnostic_guardrails"] = {
                "comparison": comparison,
                "failures": comparison_failures(comparison, config["promotion"]),
                "interpretation": "Diagnostic only; passing cannot establish prospective eligibility",
            }
            cell["review_gate"] = review_gate(
                {
                    "prospective": False,
                    "locked_before_outcomes": False,
                    "comparators_preregistered": True,
                    "identical_cohorts": True,
                    "coherent": True,
                    "races": 0,
                    "blocks": 0,
                    "shadow_races": 0,
                    "comparisons": {"baseline": comparison},
                    "unresolved_failures": True,
                },
                config,
            )
        report["horizons"][horizon] = section
    return report
