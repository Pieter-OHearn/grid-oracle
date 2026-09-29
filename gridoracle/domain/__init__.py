"""Versioned, provider-independent motorsport domain contracts."""

from .results import (
    CanonicalResultStatus,
    ResultClassification,
    classify_result,
    rankable_target_rows,
)
from .targets import TARGET_POLICY_VERSION, ForecastHorizon, target_policy

__all__ = [
    "TARGET_POLICY_VERSION",
    "CanonicalResultStatus",
    "ForecastHorizon",
    "ResultClassification",
    "classify_result",
    "rankable_target_rows",
    "target_policy",
]
