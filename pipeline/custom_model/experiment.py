"""Bounded frozen-WP06 comparison. Select on tune, calibrate, then score once."""

from __future__ import annotations

import argparse
import gzip
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from pipeline.benchmark.artifacts import (
    BENCHMARK,
    CONTRACT,
    ROOT,
    canonical,
    digest,
    file_hash,
    read_json,
    verify_lock,
    write_bytes_once,
    write_once,
)
from pipeline.benchmark.contracts import verify_feature_values, verify_inputs
from pipeline.benchmark.data import KEY, load_dataset
from pipeline.benchmark.evaluation import evaluate_predictions
from pipeline.benchmark.fitting import fit_calibrator, fit_in_block
from pipeline.benchmark.metrics import aggregate, score_race
from pipeline.benchmark.report import score_baseline, slice_report, slice_tags
from pipeline.benchmark.runtime import git, source_hashes
from pipeline.benchmark.uncertainty import uncertainty
from pipeline.custom_model.backend import device, hardware, memory, synchronize
from pipeline.custom_model.data import FEATURES, scores
from pipeline.custom_model.training import train

CONFIG = ROOT / "docs/research/wp08/config.json"


def labels(frame, targets, kind):
    result = []
    for key, rows in frame.groupby("race_key", sort=False):
        ranked = sorted((r for r in targets[key] if r["rank"] is not None), key=lambda r: r["rank"])
        ranks = {r["driver"]: i + 1 for i, r in enumerate(ranked)}
        winner = ranked[0]["driver"]
        for driver in rows[KEY]:
            result.append(
                {"race_key": key, KEY: driver, "target": ranks.get(driver) if kind == "rank" else int(driver == winner)}
            )
    return pd.DataFrame(result)


def predict(model, encoder, frame, races, backend, temperature=1.0):
    batch, keys, identities = encoder.batch(frame, races, backend=backend)
    with torch.no_grad():
        logits = scores(model, batch).cpu().double().numpy()
    result = {}
    for i, (key, ids) in enumerate(zip(keys, identities, strict=True)):
        values = logits[i, : len(ids)] / temperature
        p = np.exp(values - values.max())
        p /= p.sum()
        ordered = sorted(ids, key=lambda d: (-values[ids.index(d)], d))
        result[key] = {"order": ordered, "winner": dict(zip(ids, p.tolist(), strict=True))}
    return result


def fit_candidate(
    frame, targets, races, dataset, splits, config, fold, horizon, candidate, backend, output, purpose="train"
):
    keys = fold["train"] + (fold["tune"] if purpose == "refit" else [])
    if candidate["history"] == "last24":
        keys = keys[-24:]
    subset = frame[frame.race_key.isin(keys)].copy()
    settings = {k: config[k] for k in ("seed", "epochs", "learning_rate", "checkpoint_interval")}
    settings.update({k: candidate[k] for k in ("hidden", "interactions", "regularization", "features")})
    names = [f for f in FEATURES if f in subset]
    return fit_in_block(
        lambda _x, _y: train(subset, races, targets, settings, str(backend), checkpoint_dir=output),
        subset,
        labels(subset, targets, "rank"),
        dataset=dataset,
        splits=splits,
        fold_id=fold["id"],
        purpose=purpose,
        horizon=horizon,
        feature_names=names,
        target_kind="rank",
    )


def calibrate(model, encoder, frame, races, targets, dataset, splits, fold, config, benchmark, backend):
    cal = frame[frame.race_key.isin(fold["calibration"])]
    predictions = predict(model, encoder, cal, races, backend)
    fields = list(predictions.values())

    def fit(probability, outcome):
        # Adapter validates locked rows and winner labels; this objective gives
        # each race one log-loss observation, despite varying field sizes.
        losses = []
        for temperature in config["calibration_temperatures"]:
            offset, total = 0, 0.0
            for field in fields:
                n = len(field["winner"])
                p = np.asarray(probability[offset : offset + n]) ** (1 / temperature)
                p /= p.sum()
                y = np.asarray(outcome[offset : offset + n])
                total -= np.log(np.maximum(p[y == 1], benchmark["epsilon"])).sum()
                offset += n
            losses.append(float(total / len(fields)))
        best = min(range(len(losses)), key=losses.__getitem__)
        return config["calibration_temperatures"][best], losses

    return fit_calibrator(
        fit,
        {k: v["winner"] for k, v in predictions.items()},
        labels(cal, targets, "winner"),
        dataset=dataset,
        splits=splits,
        fold_id=fold["id"],
    )


def run(output, backend_name="cpu", config_path=CONFIG, reference_only=False):
    run_id = "wp08-" + uuid.uuid4().hex
    root = Path(output) / run_id
    root.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    write_once(
        root / "started.json",
        {"run_id": run_id, "requested_backend": backend_name, "config_path": str(config_path), "status": "started"},
    )
    try:
        verify_lock()
        config = read_json(Path(config_path))
        # The registered bounded design is read-only once committed.
        if digest(config) != digest(read_json(CONFIG)):
            raise ValueError("configuration differs from registered WP08 design")
        benchmark = read_json(CONTRACT / "config.json")
        dataset = read_json(BENCHMARK / "dataset.json")
        splits = read_json(BENCHMARK / "splits.json")
        fingerprints = verify_inputs(dataset, splits, benchmark)
        code_files = {
            **source_hashes(),
            **{str(p.relative_to(ROOT)): file_hash(p) for p in sorted((ROOT / "pipeline/custom_model").glob("*.py"))},
            "pipeline/tests/test_custom_model.py": file_hash(ROOT / "pipeline/tests/test_custom_model.py"),
        }
        backend = device(backend_name)
        write_once(
            root / "manifest.json",
            {
                "run_id": run_id,
                "hardware": hardware(),
                "backend": str(backend),
                "git_revision": git("rev-parse", "HEAD"),
                "git_dirty": bool(git("status", "--porcelain")),
                "code_files": code_files,
                "code_sha256": digest(code_files),
                "frozen_inputs": fingerprints,
                "research_config": config,
                "research_config_sha256": file_hash(Path(config_path)),
                "research_dependencies_sha256": file_hash(ROOT / "docs/research/wp08/requirements-macos.txt"),
                "threads": {"torch": 1},
                "seed": config["seed"],
            },
        )
        frames, targets, rebuilt = load_dataset(root / "scratch")
        if digest(rebuilt) != digest(dataset):
            raise ValueError("dataset reconstruction changed")
        races = {r["race"]: r for r in dataset["races"]}
        selections, predictions, validation, timings = [], {}, [], []
        families = {"reference": config["reference_candidates"]}
        if not reference_only:
            families["nonlinear"] = config["challenger_candidates"]
        # All family/fold/horizon decisions are frozen before ANY outer scoring.
        for horizon, frame in frames.items():
            verify_feature_values(frame, horizon, dataset)
            for family, candidates in families.items():
                predictions[horizon, family] = {}
                for fold in splits["folds"]:
                    tune = frame[frame.race_key.isin(fold["tune"])]
                    trials = []
                    for candidate in candidates:
                        trial_root = root / "checkpoints" / horizon / family / fold["id"] / candidate["id"]
                        begin = time.perf_counter()
                        model, enc, curve = fit_candidate(
                            frame,
                            targets,
                            races,
                            dataset,
                            splits,
                            config,
                            fold,
                            horizon,
                            candidate,
                            backend,
                            trial_root,
                        )
                        guessed = predict(model, enc, tune, races, backend)
                        records = [
                            score_race(targets[k], p, races[k]["drivers"], benchmark) for k, p in guessed.items()
                        ]
                        metrics = aggregate(records, len(fold["tune"]), benchmark["calibration_bins"])
                        trials.append((metrics["metrics"]["winner_log_loss"], candidate))
                        validation.append(
                            {
                                "horizon": horizon,
                                "family": family,
                                "fold": fold["id"],
                                "candidate": candidate["id"],
                                "config": candidate,
                                "validation": metrics,
                                "curve": curve,
                                "parameters": sum(p.numel() for p in model.parameters()),
                            }
                        )
                        timings.append(
                            {
                                "horizon": horizon,
                                "family": family,
                                "fold": fold["id"],
                                "candidate": candidate["id"],
                                "training_seconds": time.perf_counter() - begin,
                            }
                        )
                    _, selected = min(trials, key=lambda t: t[0])
                    model, enc, curve = fit_candidate(
                        frame,
                        targets,
                        races,
                        dataset,
                        splits,
                        config,
                        fold,
                        horizon,
                        selected,
                        backend,
                        root / "checkpoints" / horizon / family / fold["id"] / "refit",
                        "refit",
                    )
                    temperature, losses = calibrate(
                        model, enc, frame, races, targets, dataset, splits, fold, config, benchmark, backend
                    )
                    decision = {
                        "horizon": horizon,
                        "family": family,
                        "fold": fold["id"],
                        "selected": selected,
                        "temperature": temperature,
                        "calibration_losses": losses,
                        "refit_curve": curve,
                    }
                    write_once(root / "decisions" / f"{horizon}-{family}-{fold['id']}.json", decision)
                    selections.append(decision)
                    evaluation = frame[frame.race_key.isin(fold["evaluation"])]
                    begin = time.perf_counter()
                    predictions[horizon, family].update(predict(model, enc, evaluation, races, backend, temperature))
                    synchronize(backend)
                    timings.append(
                        {
                            "horizon": horizon,
                            "family": family,
                            "fold": fold["id"],
                            "inference_seconds_per_race": (time.perf_counter() - begin) / len(fold["evaluation"]),
                        }
                    )
        write_once(root / "selection-frozen.json", {"selections": selections, "validation": validation})
        result = {
            "interpretation": dataset["quality"],
            "validation": validation,
            "selections": selections,
            "exploratory": {},
            "asof": {"expected_races": 70, "eligible_races": 0, "coverage": 0.0, "winner_log_loss": None},
            "prospective": {"status": "pending_calendar_enrollment", "winner_log_loss": None},
            "promotion": {"promoted": False, "reason": "WP09 review and prospective evidence required"},
        }
        for (horizon, family), guessed in predictions.items():
            scored = evaluate_predictions(guessed, targets, dataset, splits, benchmark)
            for row in scored["races"]:
                k = row["race"]
                rows = frames[horizon][frames[horizon].race_key == k]
                row.update(
                    prediction=guessed[k],
                    slices=slice_tags(races[k], rows, targets[k]),
                    missing_feature_cells=int(rows.isna().sum().sum()),
                )
            scored["folds"] = {
                f["id"]: aggregate(
                    [r for r in scored["races"] if r["fold"] == f["id"]],
                    len(f["evaluation"]),
                    benchmark["calibration_bins"],
                )
                for f in splits["folds"]
            }
            scored["slices"] = slice_report(scored["races"], benchmark)
            scored["paired_baselines"] = {
                name: uncertainty(
                    scored["races"],
                    benchmark,
                    score_baseline(name, horizon, frames, targets, dataset, splits, benchmark),
                )
                for name in benchmark["baselines"][horizon]
            }
            result["exploratory"][f"{horizon}/{family}"] = scored
        if not reference_only:
            result["paired_reference_minus_nonlinear"] = {
                h: uncertainty(
                    result["exploratory"][f"{h}/nonlinear"]["races"],
                    benchmark,
                    result["exploratory"][f"{h}/reference"]["races"],
                )
                for h in frames
            }
        if any(file_hash(ROOT / path) != expected for path, expected in code_files.items()):
            raise RuntimeError("source changed during experiment; discard performance interpretation")
        write_bytes_once(root / "report.json.gz", gzip.compress(canonical(result), mtime=0))
        artifacts = {
            str(p.relative_to(root)): file_hash(p)
            for p in sorted(root.rglob("*"))
            if p.is_file() and "scratch" not in p.parts
        }
        synchronize(backend)
        write_once(
            root / "finished.json",
            {
                "run_id": run_id,
                "status": "success",
                "runtime_seconds": time.perf_counter() - started,
                "memory": memory(backend),
                "timings": timings,
                "result_sha256": digest(result),
                "artifacts": artifacts,
            },
        )
        return root
    except BaseException as error:
        try:
            write_once(
                root / "failed.json",
                {
                    "run_id": run_id,
                    "status": "failed",
                    "error": f"{type(error).__name__}: {error}",
                    "runtime_seconds": time.perf_counter() - started,
                },
            )
        except Exception as recording_error:
            error.add_note(f"failure recording also failed: {recording_error}")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=["cpu", "cuda", "mps", "auto"], default="cpu")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--reference-only", action="store_true")
    args = parser.parse_args()
    print(run(args.output, args.backend, args.config, args.reference_only))


if __name__ == "__main__":
    main()
