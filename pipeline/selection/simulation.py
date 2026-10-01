"""Retain numerical validation of the conditional sampler, not race evidence."""

from itertools import permutations

import numpy as np

from pipeline.selection.outputs import Field, joint_distribution


def validation_evidence():
    field = Field("synthetic", "pre_weekend", "2026-01-01T00:00:00+00:00", "fixture", ("a", "b", "c"))
    p = np.array([0.5, 0.3, 0.2])
    prediction = {"order": list(field.entries), "winner": dict(zip(field.entries, p.tolist(), strict=True))}
    exact = np.zeros((3, 3))
    for order in permutations(range(3)):
        mass = 1.0
        remaining = list(range(3))
        for i in order:
            mass *= p[i] / p[remaining].sum()
            remaining.remove(i)
        for rank, i in enumerate(order):
            exact[i, rank] += mass
    convergence = []
    for n in (64, 512, 4096):
        errors = []
        for seed in range(12):
            observed = joint_distribution(field, prediction, seed=seed, per_winner=n)["matrix"]
            errors.append(float(np.square(observed - exact).sum()))
        convergence.append({"samples_per_winner": n, "seeds": 12, "mean_squared_matrix_error": float(np.mean(errors))})
    return {
        "scope": "synthetic numerical checks only; never prospective race observations",
        "exact_three_entry_rank_marginals": exact.tolist(),
        "convergence": convergence,
        "coherence": "permutation, nested marginal and slot-sum assertions run for every decoded field",
        "cross_entry_dependence": "one winner and fixed top-k slots per draw; tested negative indicator covariance",
        "richer_simulator": "not implemented or released",
    }
