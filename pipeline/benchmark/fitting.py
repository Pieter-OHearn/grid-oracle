"""Fit only with lock-verified inputs and separate feature/calibration scopes."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from pipeline.benchmark.contracts import verify_feature_values, verify_inputs, verify_label_values
from pipeline.benchmark.data import KEY
from pipeline.benchmark.metrics import validate_cohort
from pipeline.benchmark.splits import (
    evaluation_start,
    fold_by_id,
    validate_fit_rows,
    validate_label_availability,
    validate_splits,
)
from pipeline.benchmark.temporal import timestamp, validate_features
from pipeline.dataset.historical import FeatureHorizon, FeatureRegistry


def checked_labels(
    labels: pd.DataFrame,
    ids: list,
    fold: dict,
    dataset: dict,
    cutoff: str | None,
    target_kind: str,
    *,
    require_availability: bool = False,
) -> pd.DataFrame:
    if labels.columns.has_duplicates or labels.duplicated(["race_key", KEY]).any():
        raise ValueError("duplicate fitting labels or columns")
    indexed = labels.set_index(["race_key", KEY])
    if set(indexed.index) != set(ids):
        raise ValueError("fitting labels and feature/prediction rows differ")
    deadline = evaluation_start(fold, dataset)
    if cutoff is not None and timestamp(cutoff) != timestamp(deadline):
        raise ValueError("caller cutoff differs from pinned evaluation start")
    if "available_at" in labels:
        validate_label_availability(labels.available_at.tolist(), deadline)
    elif require_availability:
        raise ValueError("as-of fitting requires label availability")
    verify_label_values(labels, dataset, target_kind)
    return indexed.loc[ids]


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
    config: dict | None = None,
    target_kind: str = "winner",
    asof_evidence: dict | None = None,
    evaluation_cutoff: str | None = None,
):
    """Fit feature models only on train or explicit train+tune refit rows.

    Inputs/feature values/labels must match the registered contract. Winner labels
    are binary by default; `target_kind='rank'` selects contiguous classified ranks
    with missing labels for unclassified entries. Calibration uses fit_calibrator.
    """
    verify_inputs(dataset, splits, config)
    validate_splits(splits, dataset)
    fold = fold_by_id(splits, fold_id)
    if purpose == "tune":
        raise ValueError("tuning is scoring-only; use explicit refit after configuration selection")
    if purpose not in {"train", "refit"}:
        raise ValueError("feature models cannot fit calibration data; use fit_calibrator")
    validate_features(frame, horizon, evidence=asof_evidence, dataset=dataset)
    ids = list(frame[["race_key", KEY]].itertuples(index=False, name=None))
    validate_fit_rows(ids, fold, dataset, purpose)
    verify_feature_values(frame, horizon, dataset)
    aligned = checked_labels(
        labels, ids, fold, dataset, evaluation_cutoff, target_kind, require_availability=asof_evidence is not None
    )
    allowed = {d.name for d in FeatureRegistry.audited_default().enabled_for(FeatureHorizon(horizon))}
    if not feature_names or len(set(feature_names)) != len(feature_names) or not set(feature_names) <= allowed:
        raise ValueError("only unique registered features may enter the estimator")
    return fit(frame[feature_names].copy(), aligned.target.to_numpy(copy=True))


def fit_calibrator(
    fit: Callable,
    predictions: dict,
    labels: pd.DataFrame,
    *,
    dataset: dict,
    splits: dict,
    fold_id: str,
    config: dict | None = None,
    evaluation_cutoff: str | None = None,
):
    """Fit winner probabilities exclusively on frozen calibration races/labels.

    When available_at is supplied it must precede the pinned evaluation start;
    caller cutoffs cannot waive or extend that deadline. Archived labels without
    verified availability remain exploratory, never as-of evidence.
    """
    verify_inputs(dataset, splits, config)
    validate_splits(splits, dataset)
    fold = fold_by_id(splits, fold_id)
    fields = {r["race"]: r["drivers"] for r in dataset["races"]}
    ids = [(race, driver) for race, probability in predictions.items() for driver in probability]
    validate_fit_rows(ids, fold, dataset, "calibration")
    indexed = checked_labels(labels, ids, fold, dataset, evaluation_cutoff, "winner")
    probabilities, outcomes = [], []
    for race, probability in predictions.items():
        expected = fields[race]
        synthetic = [{"driver": driver, "rank": None} for driver in expected]
        validate_cohort(synthetic, expected, expected, probability)
        actual = indexed.loc[[(race, driver) for driver in expected]]
        probabilities.extend(probability[driver] for driver in expected)
        outcomes.extend(actual.target.tolist())
    return fit(probabilities, outcomes)
