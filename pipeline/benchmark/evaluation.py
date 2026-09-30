"""Common frozen-cohort entry point for baseline and future challenger outputs."""

from __future__ import annotations

from pipeline.benchmark.artifacts import digest
from pipeline.benchmark.contracts import verify_inputs
from pipeline.benchmark.metrics import aggregate, score_race
from pipeline.benchmark.splits import validate_splits
from pipeline.benchmark.uncertainty import uncertainty


def evaluate_predictions(predictions: dict, targets: dict, dataset: dict, splits: dict, config: dict) -> dict:
    """Evaluate outputs only; this function cannot fit, tune or promote a model.

    Missing races remain explicit coverage failures. Missing entrants within a
    supplied race are rejected. Paired comparison refuses different race cohorts.
    Labels are checked against the frozen manifest before any score is computed.
    """
    fingerprints = verify_inputs(dataset, splits, config)
    validate_splits(splits, dataset)
    races = {r["race"]: r for r in dataset["races"]}
    expected = [key for fold in splits["folds"] for key in fold["evaluation"]]
    if not set(predictions) <= set(expected):
        raise ValueError("prediction contains a race outside the frozen evaluation")
    records, missing = [], []
    for fold in splits["folds"]:
        for index, key in enumerate(fold["evaluation"]):
            if key not in targets or digest(targets[key]) != races[key]["target_sha256"]:
                raise ValueError("evaluation target differs from frozen cohort")
            if key not in predictions:
                missing.append({"race": key, "reason": "no prediction supplied"})
                continue
            score = score_race(targets[key], predictions[key], races[key]["drivers"], config)
            score.update(race=key, fold=fold["id"], block=f"{fold['id']}:{index // config['block_races']}")
            records.append(score)
    return {
        "input_fingerprints": fingerprints,
        "summary": aggregate(records, len(expected), config["calibration_bins"]),
        "races": records,
        "missing": missing,
        "loss_uncertainty": uncertainty(records, config),
        "interpretation": dataset["quality"],
        "promotion": "not authorized by scoring",
    }
