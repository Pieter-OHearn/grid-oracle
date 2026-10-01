"""Replay fixed winner calibration on prior held-out predictions, never test rows."""

from __future__ import annotations

from pipeline.benchmark.artifacts import digest
from pipeline.benchmark.contracts import verify_inputs
from pipeline.benchmark.fitting import fit_calibrator
from pipeline.benchmark.splits import evaluation_start, fold_by_id
from pipeline.challengers.decoder import choose_power


def fit_winner_calibration(predictions, labels, *, fit_races, fold, dataset, splits, config, powers):
    verify_inputs(dataset, splits, config)
    registered = fold_by_id(splits, fold["id"])
    if fold != registered:
        raise ValueError("fold differs from registered split")
    fold = registered
    calibration = set(fold["calibration"])
    if set(predictions) != calibration or set(fit_races) & calibration:
        raise ValueError("calibration requires every held-out calibration race and no training overlap")
    if not fit_races or not set(fit_races) <= set(fold["train"] + fold["tune"]):
        raise ValueError("weights fitted outside the allowed pre-calibration block")
    sizes = [len(p) for p in predictions.values()]
    fitted = fit_calibrator(
        lambda p, y: choose_power(p, y, sizes, powers),
        predictions,
        labels,
        dataset=dataset,
        splits=splits,
        fold_id=fold["id"],
        config=config,
    )
    return {
        **fitted,
        "method": "winner_power_pl",
        "objective": "equal_race_winner_log_loss",
        "predictions_sha256": digest(predictions),
        "calibration_races": fold["calibration"],
        "fit_races": fit_races,
        "deadline": evaluation_start(fold, dataset),
        "out_of_sample": True,
        "asof_eligible": False,
        "scope": "frozen historical reconstruction; label availability unverified",
        "conditional_top_k": "derived jointly; no separate official top-k calibration claim",
    }
