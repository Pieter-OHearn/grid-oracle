"""A joint conditional PL distribution; never independent top-k classifiers.

Stratifying by the first finisher preserves the input winner marginal exactly.
Each suffix is sampled without replacement. All rank/top-k marginals come from
these same weighted permutations, so nesting and field sums hold by construction.
This is conditional on a fixed field completing, not an official censoring model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from pipeline.benchmark.artifacts import digest
from pipeline.benchmark.metrics import validate_cohort
from pipeline.benchmark.temporal import timestamp

HORIZONS = {"pre_weekend", "post_qualifying"}


@dataclass(frozen=True)
class Field:
    race: str
    horizon: str
    cutoff: str
    revision: str
    entries: tuple[str, ...]
    provenance: str = "verified"
    teams: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        if self.provenance == "verified":
            timestamp(self.cutoff)
        elif self.provenance != "exploratory" or self.cutoff not in {
            "before_first_competitive_session",
            "after_verified_qualifying_before_race",
        }:
            raise ValueError("unverified cutoff must retain its explicit historical marker")
        if self.horizon not in HORIZONS or not self.race or not self.revision:
            raise ValueError("race, horizon and entry revision are required")
        if not self.entries or len(set(self.entries)) != len(self.entries) or any(not e for e in self.entries):
            raise ValueError("field requires unique nonempty entry identities")
        object.__setattr__(self, "entries", tuple(sorted(self.entries)))
        object.__setattr__(self, "teams", tuple(sorted(self.teams)))
        if self.teams and (len(self.teams) != len(self.entries) or {e for e, _ in self.teams} != set(self.entries)):
            raise ValueError("team mapping differs from entry field")

    @property
    def sha256(self):
        return digest(asdict(self))

    def check(self, prediction):
        validate_cohort(
            [{"driver": e, "rank": None} for e in self.entries],
            prediction["order"],
            list(self.entries),
            prediction["winner"],
        )


def validate_joint(matrix, winner):
    a = np.asarray(matrix, dtype=float)
    p = np.asarray(winner, dtype=float)
    if a.shape != (len(p), len(p)) or not len(p) or not np.isfinite(a).all():
        raise ValueError("invalid rank marginal shape or nonfinite probability")
    if (a < 0).any() or (a > 1).any():
        raise ValueError("rank probabilities outside [0,1]")
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("invalid winner probabilities")
    if not np.allclose(a.sum(axis=0), 1, atol=1e-10, rtol=0) or not np.allclose(a.sum(axis=1), 1, atol=1e-10, rtol=0):
        raise ValueError("rank distribution is not field coherent")
    if not np.allclose(a[:, 0], p, atol=1e-10, rtol=0):
        raise ValueError("winner and joint rank probabilities disagree")


def joint_distribution(field: Field, prediction: dict, *, seed: int, per_winner: int = 512) -> dict:
    field.check(prediction)
    if isinstance(per_winner, bool) or not isinstance(per_winner, int) or per_winner < 1:
        raise ValueError("positive integer suffix sample count required")
    ids = field.entries
    p = np.asarray([prediction["winner"][d] for d in ids])
    n = len(ids)
    rng = np.random.default_rng(seed)
    draws, weights = [], []
    matrix = np.zeros((n, n))
    for first in np.flatnonzero(p > 0):
        remaining = np.delete(np.arange(n), first)
        # Zero-strength entries finish after positive entries, uniformly ordered.
        # This is the explicit limiting PL completion policy, not a DNF label.
        logits = np.full(len(remaining), -1e6)
        positive = p[remaining] > 0
        logits[positive] = np.log(p[remaining][positive])
        noise = rng.gumbel(size=(per_winner, len(remaining)))
        suffix = remaining[np.argsort(-(logits + noise), axis=1, kind="stable")]
        sample = np.column_stack((np.full(per_winner, first, dtype=int), suffix))
        if not np.all(np.sort(sample, axis=1) == np.arange(n)):
            raise ValueError("rank draw is not a field permutation")
        for rank in range(n):
            matrix[:, rank] += p[first] * np.bincount(sample[:, rank], minlength=n) / per_winner
        draws.append(sample)
        weights.append(np.full(per_winner, p[first] / per_winner))
    validate_joint(matrix, p)
    return {"matrix": matrix, "draws": np.concatenate(draws), "weights": np.concatenate(weights)}


def bounded_sum(values):
    value = float(np.sum(values))
    if not np.isfinite(value) or value < -1e-10 or value > 1 + 1e-10:
        raise ValueError("invalid marginal probability")
    # Only remove floating summation roundoff from a validated joint matrix.
    # Winner probabilities and WP06 scoring inputs are never clipped/repaired.
    return min(1.0, max(0.0, value))


def coherent_output(field: Field, prediction: dict, lineage: dict, *, seed=6062026, per_winner=512) -> dict:
    joint = joint_distribution(field, prediction, seed=seed, per_winner=per_winner)
    a = joint["matrix"]
    result = {
        "schema": "wp09-forecast-v1",
        "field": asdict(field),
        "field_sha256": field.sha256,
        "lineage": lineage,
        "order": prediction["order"],
        "target": "fixed_field_completion_conditional_pl",
        "winner": prediction["winner"],
        "rank_marginals": {e: a[i].tolist() for i, e in enumerate(field.entries)},
        "conditional_top3": {e: bounded_sum(a[i, :3]) for i, e in enumerate(field.entries)},
        "conditional_top10": {e: bounded_sum(a[i, :10]) for i, e in enumerate(field.entries)},
        "official_top3": None,
        "official_top10": None,
        "points": None,
        "retirement": None,
        "simulation": {
            "algorithm": "winner_stratified_gumbel_pl_v1",
            "seed": seed,
            "suffix_samples_per_positive_winner": per_winner,
            "draws": len(joint["draws"]),
            # Upper bound on individual marginal Monte Carlo SE; not model uncertainty.
            "marginal_mc_se_upper_bound": float(
                np.sqrt(sum(v * v for v in prediction["winner"].values()) / (4 * per_winner))
            ),
        },
        "publication_eligible": False,
        "limitations": "Conditional top-k is not calibrated official top-k; selection does not authorize publication.",
    }
    validate_output(result, field)
    return result


def validate_output(output: dict, expected_field: Field):
    if (
        output.get("schema") != "wp09-forecast-v1"
        or output.get("target") != "fixed_field_completion_conditional_pl"
        or output.get("publication_eligible") is not False
    ):
        raise ValueError("unsupported target/schema or unapproved publication claim")
    if output["field_sha256"] != expected_field.sha256 or digest(output["field"]) != expected_field.sha256:
        raise ValueError("entry/cutoff revision changed; create a new run, never rewrite history")
    expected_field.check(output)
    ids = expected_field.entries
    if set(output["rank_marginals"]) != set(ids):
        raise ValueError("rank marginal entries differ")
    a = np.array([output["rank_marginals"][e] for e in ids])
    validate_joint(a, [output["winner"][e] for e in ids])
    last = np.array([output["winner"][e] for e in ids])
    for name, k in (("conditional_top3", 3), ("conditional_top10", 10)):
        if set(output[name]) != set(ids):
            raise ValueError("top-k entries differ")
        current = np.array([output[name][e] for e in ids])
        if not np.isfinite(current).all() or (current < 0).any() or (current > 1).any():
            raise ValueError("invalid top-k probability")
        if (current + 1e-10 < last).any() or not np.allclose(current, a[:, :k].sum(axis=1), atol=1e-10, rtol=0):
            raise ValueError("top-k is not nested or differs from joint distribution")
        if abs(current.sum() - min(k, len(ids))) > 1e-10:
            raise ValueError("top-k field sum invalid")
        last = current
    if any(output[name] is not None for name in ("official_top3", "official_top10", "points", "retirement")):
        raise ValueError("unsupported official outcome probability")
