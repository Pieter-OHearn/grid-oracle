"""One target/cohort contract shared by every benchmark contender."""

from __future__ import annotations

import math

import numpy as np

from pipeline.benchmark.artifacts import digest

SCALARS = (
    "winner_log_loss",
    "winner_brier",
    "winner_hit",
    "rank_mae",
    "rank_correlation",
    "top3_overlap",
    "top10_overlap",
)


def validate_cohort(targets: list[dict], order: list[str], expected: list[str], probability: dict | None) -> None:
    actual = [r["driver"] for r in targets]
    if len(set(expected)) != len(expected) or not expected:
        raise ValueError("empty or duplicate expected field")
    if len(actual) != len(expected) or set(actual) != set(expected):
        raise ValueError("target cohort mismatch")
    if len(order) != len(expected) or set(order) != set(expected):
        raise ValueError("prediction cohort mismatch; never silently intersect")
    if probability is not None:
        if set(probability) != set(expected):
            raise ValueError("probability cohort mismatch")
        p = np.array(list(probability.values()), dtype=float)
        if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any() or abs(p.sum() - 1) > 1e-10:
            raise ValueError("incoherent winner probability distribution")
    ranks = [row["rank"] for row in targets if row["rank"] is not None]
    if len(set(ranks)) != len(ranks) or any(not isinstance(r, int) or r < 1 for r in ranks):
        raise ValueError("ambiguous official classified ranks")


def reliability(probability: dict, winner: str, bins: int) -> list[dict]:
    records = [{"weight": 0.0, "predicted_sum": 0.0, "observed_sum": 0.0} for _ in range(bins)]
    weight = 1 / len(probability)
    for driver, p in probability.items():
        cell = records[min(int(p * bins), bins - 1)]
        cell["weight"] += weight
        cell["predicted_sum"] += p * weight
        cell["observed_sum"] += int(driver == winner) * weight
    return records


def score_race(targets: list[dict], prediction: dict, expected: list[str], config: dict) -> dict:
    order, probability = prediction["order"], prediction.get("winner")
    validate_cohort(targets, order, expected, probability)
    result = dict.fromkeys(SCALARS)
    result.update(
        field_size=len(expected),
        target_sha256=digest(targets),
        cohort_sha256=digest(sorted(expected)),
        reliability=[],
    )
    classified = sorted((r for r in targets if r["rank"] is not None), key=lambda r: r["rank"])
    actual_order = [r["driver"] for r in classified]
    result["classified_entries"] = len(classified)
    if classified:
        predicted_classified = [d for d in order if d in actual_order]
        differences = [predicted_classified.index(d) - i for i, d in enumerate(actual_order)]
        result["rank_mae"] = float(np.mean(np.abs(differences)))
        n = len(classified)
        if n > 1:
            result["rank_correlation"] = 1 - 6 * sum(d * d for d in differences) / (n * (n * n - 1))
    for k in (3, 10):
        actual = {r["driver"] for r in classified if r["rank"] <= k}
        required = min(k, len(expected))
        if len(actual) == required:
            result[f"top{k}_overlap"] = len(set(order[:k]) & actual) / required
    winner = next((r["driver"] for r in classified if r["rank"] == 1), None)
    if winner is not None:
        result["winner_hit"] = float(order[0] == winner)
        if probability is not None:
            result["winner_log_loss"] = -math.log(max(config["epsilon"], probability[winner]))
            result["winner_brier"] = sum((p - int(d == winner)) ** 2 for d, p in probability.items())
            result["reliability"] = reliability(probability, winner, config["calibration_bins"])
    return result


def aggregate(records: list[dict], expected_races: int, bins: int) -> dict:
    if expected_races < len(records) or expected_races < 0:
        raise ValueError("invalid coverage denominator")
    metrics, counts = {}, {}
    for metric in SCALARS:
        values = [record[metric] for record in records if record[metric] is not None]
        metrics[metric] = float(np.mean(values)) if values else None
        counts[metric] = len(values)
    cells = []
    for i in range(bins):
        totals = {
            key: sum(r["reliability"][i][key] for r in records if r["reliability"])
            for key in ("weight", "predicted_sum", "observed_sum")
        }
        weight = totals["weight"]
        cells.append(
            {
                "bin": [i / bins, (i + 1) / bins],
                "race_weight": weight,
                "mean_probability": totals["predicted_sum"] / weight if weight else None,
                "observed_rate": totals["observed_sum"] / weight if weight else None,
            }
        )
    total = sum(c["race_weight"] for c in cells)
    metrics["ece"] = (
        sum(c["race_weight"] * abs(c["mean_probability"] - c["observed_rate"]) for c in cells if c["race_weight"])
        / total
        if total
        else None
    )
    return {
        "metrics": metrics,
        "metric_race_counts": counts,
        "expected_races": expected_races,
        "predicted_races": len(records),
        "coverage": len(records) / expected_races if expected_races else None,
        "winner_evaluation_coverage": counts["winner_log_loss"] / expected_races if expected_races else None,
        "reliability": cells,
    }


def display(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.6f}"
