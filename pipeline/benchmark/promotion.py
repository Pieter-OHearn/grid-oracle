"""Evidence checklist only; neither passing nor recency changes the active model."""

from __future__ import annotations

import math


def review_gate(evidence: dict, config: dict) -> dict:
    p = config["promotion"]
    reasons = []
    required = ("prospective", "locked_before_outcomes", "comparators_preregistered", "identical_cohorts", "coherent")
    for key in required:
        if evidence.get(key) is not True:
            reasons.append(f"{key} not verified")
    for key, minimum in (
        ("races", p["min_races"]),
        ("blocks", p["min_blocks"]),
        ("shadow_races", p["min_shadow_races"]),
    ):
        if not finite(evidence.get(key)) or evidence[key] < minimum:
            reasons.append(f"{key} below minimum or missing")
    for key, maximum in (
        ("seconds_per_race", p["max_inference_seconds_per_race"]),
        ("peak_rss_mib", p["max_peak_rss_mib"]),
    ):
        if not finite(evidence.get(key)) or evidence[key] > maximum:
            reasons.append(f"{key} exceeds budget or missing")
    comparisons = evidence.get("comparisons", {})
    if set(comparisons) != {"baseline", "incumbent"}:
        reasons.append("both frozen baseline and incumbent comparisons required")
    for label, comparison in comparisons.items():
        reasons.extend(f"{label}: {reason}" for reason in comparison_failures(comparison, p))
    if evidence.get("unresolved_failures", True):
        reasons.append("unresolved experiment/issuance failures")
    return {"eligible_for_independent_review": not reasons, "promoted": False, "reasons": reasons}


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def comparison_failures(comparison: dict, p: dict) -> list[str]:
    reasons = []
    improvement = comparison.get("mean_log_loss_improvement")
    lower = comparison.get("paired_block_ci_lower")
    if not finite(improvement) or improvement < p["min_mean_log_loss_improvement"]:
        reasons.append("insufficient mean winner log-loss improvement")
    if not finite(lower) or lower <= p["min_paired_ci_lower"]:
        reasons.append("paired block improvement interval inconclusive")
    limits = {
        "rank_mae_regression": p["max_rank_mae_regression"],
        "rank_correlation_drop": p["max_rank_correlation_drop"],
        "top3_overlap_drop": p["max_top_k_overlap_drop"],
        "top10_overlap_drop": p["max_top_k_overlap_drop"],
        "winner_hit_drop": p["max_winner_hit_drop"],
        "brier_regression": p["max_brier_regression"],
        "ece_regression": p["max_ece_regression"],
        "ece": p["max_ece"],
        "coverage_drop": p["max_coverage_drop"],
    }
    for key, limit in limits.items():
        if not finite(comparison.get(key)) or comparison[key] > limit:
            reasons.append(f"{key} failed or missing")
    coverage = comparison.get("coverage")
    if not finite(coverage) or coverage < p["min_coverage"]:
        reasons.append("coverage failed or missing")
    slices = comparison.get("slices")
    if not slices or comparison.get("all_predeclared_slices_present") is not True:
        reasons.append("predeclared slices missing")
    else:
        for name, cell in slices.items():
            if not finite(cell.get("races")):
                reasons.append(f"slice {name} count missing")
            elif cell["races"] >= p["slice_min_races"]:
                regression = cell.get("log_loss_regression")
                if not finite(regression) or regression > p["max_slice_log_loss_regression"]:
                    reasons.append(f"slice {name} regressed or missing")
    return reasons
