"""Regularized trees and a non-neural hierarchical PL MAP estimator."""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp
from xgboost import XGBRanker, XGBRegressor

from pipeline.benchmark.data import KEY

TEAM = "constructor_identity_key"
IDENTITIES = (KEY, TEAM)


@dataclass
class Encoder:
    names: list[str]
    medians: np.ndarray
    scales: np.ndarray
    vocabularies: dict[str, list[str]]

    @classmethod
    def fit(cls, numeric: pd.DataFrame, context: pd.DataFrame, weights: np.ndarray):
        # Zero-weight old seasons must not inform newest-season preprocessing.
        active = numeric.loc[weights > 0].astype(float)
        medians = active.median().fillna(0).to_numpy()
        scales = active.fillna(pd.Series(medians, index=numeric.columns)).std(ddof=0).fillna(1).to_numpy()
        scales[scales < 1e-8] = 1
        vocab = {key: sorted(context.loc[weights > 0, key].unique().tolist()) for key in IDENTITIES}
        return cls(numeric.columns.tolist(), medians, scales, vocab)

    def transform(self, numeric: pd.DataFrame, context: pd.DataFrame) -> np.ndarray:
        values = numeric[self.names].astype(float).to_numpy()
        missing = np.isnan(values)
        values = (np.where(missing, self.medians, values) - self.medians) / self.scales
        identities = [
            (context[key].to_numpy()[:, None] == np.asarray(self.vocabularies[key])[None, :]).astype(float)
            for key in IDENTITIES
        ]
        return np.column_stack([values, missing.astype(float), *identities])

    def artifact(self) -> dict:
        return {
            "names": self.names,
            "medians": self.medians.tolist(),
            "scales": self.scales.tolist(),
            "vocabularies": self.vocabularies,
        }

    @classmethod
    def restore(cls, value: dict):
        return cls(value["names"], np.asarray(value["medians"]), np.asarray(value["scales"]), value["vocabularies"])


def race_weights(context: pd.DataFrame, trial: dict, variant: str) -> np.ndarray:
    keys = context.race_key.drop_duplicates().tolist()
    age = {key: len(keys) - 1 - i for i, key in enumerate(keys)}
    half_life = None if variant == "no_recency" else trial["half_life"]
    weights = np.ones(len(context)) if half_life is None else np.exp2(-context.race_key.map(age).to_numpy() / half_life)
    if variant == "recent_season_pool":
        weights *= context.season.eq(context.season.max()).to_numpy()
    if not (weights > 0).any():
        raise ValueError("no positive-weight fitting races")
    return weights


def rank_groups(context: pd.DataFrame, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Masked labels; higher relevance is better; qids never cross races."""
    keep = np.isfinite(labels)
    indices = np.flatnonzero(keep)
    codes = pd.factorize(context.race_key, sort=False)[0][keep]
    if (np.diff(codes) < 0).any():
        raise ValueError("race query IDs must be contiguous and sorted")
    counts = pd.Series(codes).map(pd.Series(codes).value_counts()).to_numpy()
    relevance = counts - labels[keep]
    if len(indices) == 0 or (relevance < 0).any():
        raise ValueError("invalid classified ranks")
    return indices, codes, relevance


def pl_objective(beta: np.ndarray, x: np.ndarray, groups: list[np.ndarray], weights: list[float], penalty: float):
    loss, gradient = 0.0, np.zeros_like(beta)
    total = sum(weights)
    for indices, weight in zip(groups, weights, strict=True):
        if weight == 0:
            continue
        ordered = x[indices]
        score = ordered @ beta
        # Final remaining entrant contributes exactly zero.
        for i in range(len(indices) - 1):
            remaining = score[i:]
            normalizer = logsumexp(remaining)
            p = np.exp(remaining - normalizer)
            loss += weight * (normalizer - score[i]) / total
            gradient += weight * (p @ ordered[i:] - ordered[i]) / total
    return loss + penalty * float(beta @ beta) / 2, gradient + penalty * beta


@dataclass
class ForecastModel:
    family: str
    encoder: Encoder
    estimator: object
    optimization: dict

    @classmethod
    def fit(
        cls,
        family: str,
        numeric: pd.DataFrame,
        labels: np.ndarray,
        context: pd.DataFrame,
        trial: dict,
        variant: str,
        study: dict,
    ):
        labels = np.asarray(labels, dtype=float)
        weights = race_weights(context, trial, variant)
        encoder = Encoder.fit(numeric, context, weights)
        x = encoder.transform(numeric, context)
        indices, qids, relevance = rank_groups(context, labels)
        if family.startswith("xgb_"):
            parameters = {k: v for k, v in trial.items() if k != "half_life"}
            parameters.update(
                tree_method="hist",
                device="cpu",
                n_jobs=study["threads"],
                random_state=study["seed"],
                subsample=1.0,
                colsample_bytree=1.0,
            )
            if family == "xgb_regression":
                estimator = XGBRegressor(objective="reg:squarederror", **parameters)
                counts = pd.Series(qids).map(pd.Series(qids).value_counts()).to_numpy()
                estimator.fit(
                    x[indices],
                    labels[indices],
                    sample_weight=weights[indices] / counts * len(indices) / len(np.unique(qids)),
                )
            elif family == "xgb_ranking":
                estimator = XGBRanker(
                    objective="rank:pairwise",
                    lambdarank_pair_method="mean",
                    lambdarank_num_pair_per_sample=8,
                    **parameters,
                )
                group_weights = [float(weights[indices[qids == q]][0]) for q in np.unique(qids)]
                estimator.fit(x[indices], relevance, qid=qids, sample_weight=group_weights)
            else:
                raise ValueError("unknown tree family")
            optimization = {"status": "fixed_tree_count", "classified_rows": len(indices)}
        elif family == "hierarchical_pl":
            groups, group_weights = [], []
            for qid in np.unique(qids):
                group = indices[qids == qid]
                groups.append(group[np.argsort(labels[group], kind="stable")])
                group_weights.append(float(weights[group][0]))
            result = minimize(
                pl_objective,
                np.zeros(x.shape[1]),
                args=(x, groups, group_weights, trial["penalty"]),
                jac=True,
                method="L-BFGS-B",
                options=study["pl_optimizer"],
            )
            if not result.success:
                raise RuntimeError(f"PL optimization failed: {result.message}")
            estimator = result.x
            optimization = {
                "status": str(result.message),
                "iterations": int(result.nit),
                "objective": float(result.fun),
                "gradient_max": float(np.abs(result.jac).max()),
                "classified_rows": len(indices),
            }
        else:
            raise ValueError("unknown model family")
        return cls(family, encoder, estimator, optimization)

    def scores(self, frame: pd.DataFrame) -> np.ndarray:
        x = self.encoder.transform(frame[self.encoder.names], frame)
        if self.family == "hierarchical_pl":
            return x @ self.estimator
        score = self.estimator.predict(x).astype(float)
        return -score if self.family == "xgb_regression" else score

    def artifact(self) -> dict:
        weights = (
            self.estimator.tolist()
            if self.family == "hierarchical_pl"
            else json.loads(bytes(self.estimator.get_booster().save_raw(raw_format="json")))
        )
        return {
            "family": self.family,
            "encoder": self.encoder.artifact(),
            "weights": weights,
            "optimization": self.optimization,
        }

    @classmethod
    def restore(cls, artifact: dict):
        family = artifact["family"]
        if family == "hierarchical_pl":
            estimator = np.asarray(artifact["weights"])
        else:
            estimator = XGBRegressor() if family == "xgb_regression" else XGBRanker()
            estimator.load_model(bytearray(json.dumps(artifact["weights"]).encode()))
        return cls(family, Encoder.restore(artifact["encoder"]), estimator, artifact["optimization"])
