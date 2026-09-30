"""Common ordinal PL winner decoder, calibrated only on permitted races."""

from __future__ import annotations

import numpy as np
import pandas as pd


def decode(drivers: list[str], scores: np.ndarray, temperature: float = 4.0) -> dict:
    scores = np.asarray(scores, dtype=float)
    if len(drivers) != len(scores) or not len(drivers) or len(set(drivers)) != len(drivers):
        raise ValueError("decoder requires a unique nonempty field")
    if not np.isfinite(scores).all() or not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("nonfinite scores or invalid temperature")
    ranks = pd.Series(-scores).rank(method="average").to_numpy() - 1
    strengths = np.exp(-ranks / temperature)
    probabilities = strengths / strengths.sum()
    order = sorted(range(len(drivers)), key=lambda i: (-scores[i], drivers[i]))
    return {
        "order": [drivers[i] for i in order],
        "winner": dict(zip(drivers, probabilities.tolist(), strict=True)),
    }


def power_probability(probability: dict, power: float) -> dict:
    if not np.isfinite(power) or power <= 0:
        raise ValueError("calibration power must be finite and positive")
    p = np.asarray(list(probability.values()), dtype=float)
    if not np.isfinite(p).all() or (p <= 0).any() or abs(p.sum() - 1) > 1e-10:
        raise ValueError("power calibration requires positive coherent base probabilities")
    logp = power * np.log(p)
    p = np.exp(logp - logp.max())
    return dict(zip(probability, (p / p.sum()).tolist(), strict=True))


def choose_power(probabilities: list, outcomes: list, sizes: list[int], powers: list[float]) -> dict:
    """Called by WP06's verified calibrator adapter; field boundaries are fixed."""
    if sum(sizes) != len(probabilities) or len(outcomes) != len(probabilities):
        raise ValueError("calibration field sizes differ")
    trials = []
    for power in powers:
        offset, losses = 0, []
        for size in sizes:
            p = probabilities[offset : offset + size]
            y = np.asarray(outcomes[offset : offset + size])
            calibrated = power_probability(dict(enumerate(p)), power)
            if y.sum() != 1:
                raise ValueError("calibration field requires one winner")
            losses.append(-np.log(calibrated[int(np.argmax(y))]))
            offset += size
        trials.append({"power": power, "winner_log_loss": float(np.mean(losses))})
    best = min(range(len(trials)), key=lambda i: (trials[i]["winner_log_loss"], i))
    return {"power": trials[best]["power"], "trials": trials}


def calibrate(prediction: dict, power: float) -> dict:
    return {"order": prediction["order"], "winner": power_probability(prediction["winner"], power)}
