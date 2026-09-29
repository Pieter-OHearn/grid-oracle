"""Guarded adapter for future training and calibration consumers of frozen splits."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from pipeline.benchmark.data import KEY
from pipeline.benchmark.splits import validate_fit_rows, validate_label_availability, validate_splits
from pipeline.benchmark.temporal import validate_features


def fit_in_block(
    fit: Callable,
    frame: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    dataset: dict,
    splits: dict,
    fold_id: str,
    purpose: str,
    horizon: str,
    feature_names: list[str],
    asof_evidence: dict | None = None,
    evaluation_cutoff: str | None = None,
):
    """Validate actual fitting row identities before calling any user estimator.

    Callers supply labels separately, indexed by race/driver, with a `target`
    column and (for as-of runs) `available_at`. The adapter never supplies labels
    to inference. Archived exploratory callers cannot claim as-of provenance.
    """
    if purpose == "tune":
        raise ValueError("tuning is scoring-only; use explicit refit after configuration selection")
    validate_splits(splits, dataset)
    fold = next(f for f in splits["folds"] if f["id"] == fold_id)
    validate_features(frame, horizon, evidence=asof_evidence)
    ids = list(frame[["race_key", KEY]].itertuples(index=False, name=None))
    validate_fit_rows(ids, fold, dataset, purpose)
    if labels.duplicated(["race_key", KEY]).any():
        raise ValueError("duplicate fitting labels")
    indexed = labels.set_index(["race_key", KEY])
    if set(indexed.index) != set(ids):
        raise ValueError("fitting labels and feature rows differ")
    aligned = indexed.loc[ids]
    if asof_evidence is not None:
        if evaluation_cutoff is None:
            raise ValueError("as-of fitting needs the first evaluation cutoff")
        validate_label_availability(aligned.available_at.tolist(), evaluation_cutoff)
    from pipeline.dataset.historical import FeatureHorizon, FeatureRegistry

    allowed = {d.name for d in FeatureRegistry.audited_default().enabled_for(FeatureHorizon(horizon))}
    if not feature_names or not set(feature_names) <= allowed:
        raise ValueError("only registered features may enter the estimator")
    return fit(frame[feature_names].copy(), aligned.target.to_numpy(copy=True))


def fit_calibrator(
    fit: Callable,
    predictions: dict,
    labels: pd.DataFrame,
    *,
    dataset: dict,
    splits: dict,
    fold_id: str,
    evaluation_cutoff: str | None = None,
):
    """Fit a probability calibrator exclusively on the declared calibration block.

    A supplied evaluation cutoff enables the same verified label-availability
    gate as as-of model fitting. Inputs are frozen base-model winner outputs;
    the callback receives probability/label arrays, never evaluation predictions.
    """
    from pipeline.benchmark.metrics import validate_cohort

    validate_splits(splits, dataset)
    fold = next(f for f in splits["folds"] if f["id"] == fold_id)
    fields = {r["race"]: r["drivers"] for r in dataset["races"]}
    ids = [(race, driver) for race, probability in predictions.items() for driver in probability]
    validate_fit_rows(ids, fold, dataset, "calibration")
    if labels.duplicated(["race_key", KEY]).any():
        raise ValueError("duplicate calibration labels")
    indexed = labels.set_index(["race_key", KEY])
    if set(indexed.index) != set(ids):
        raise ValueError("calibration labels and predictions differ")
    probabilities, outcomes = [], []
    for race, probability in predictions.items():
        expected = fields[race]
        synthetic = [{"driver": driver, "rank": None} for driver in expected]
        validate_cohort(synthetic, expected, expected, probability)
        actual = indexed.loc[[(race, driver) for driver in expected]]
        if not actual.target.isin([0, 1]).all() or actual.target.sum() != 1:
            raise ValueError("calibration requires exactly one winner per race")
        probabilities.extend(probability[driver] for driver in expected)
        outcomes.extend(actual.target.tolist())
    if evaluation_cutoff is not None:
        validate_label_availability(indexed.available_at.tolist(), evaluation_cutoff)
    return fit(probabilities, outcomes)
