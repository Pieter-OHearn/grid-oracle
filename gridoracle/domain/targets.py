"""Forecast horizons and target contracts.

This module deliberately contains no provider or database code.  Consumers use
the versioned policy as the single definition of what information is allowed at
each prediction cutoff and which final results can become ranking labels.
"""

from dataclasses import dataclass
from enum import StrEnum

TARGET_POLICY_VERSION = "2026.1"


class ForecastHorizon(StrEnum):
    """Products whose information cutoffs and scorecards must not be mixed."""

    PRE_WEEKEND = "pre_weekend"
    POST_QUALIFYING = "post_qualifying"


@dataclass(frozen=True)
class TargetPolicy:
    """The immutable label contract for a forecast horizon."""

    version: str
    horizon: ForecastHorizon
    information_cutoff: str
    prediction_deadline: str
    target: str
    excluded_result_statuses: tuple[str, ...]


_POLICIES = {
    ForecastHorizon.PRE_WEEKEND: TargetPolicy(
        version=TARGET_POLICY_VERSION,
        horizon=ForecastHorizon.PRE_WEEKEND,
        information_cutoff=(
            "The event's verified race-weekend publication cutoff. No session "
            "result, grid, or data first available after that timestamp is eligible."
        ),
        prediction_deadline=(
            "Publish before the weekend's first scheduled competitive session; "
            "a later schedule revision creates a new cutoff revision, never "
            "an overwrite."
        ),
        target=(
            "Officially classified race finishing order, normalized to contiguous "
            "internal ranks only for target-eligible classified entrants."
        ),
        excluded_result_statuses=("dns", "dsq", "unknown"),
    ),
    ForecastHorizon.POST_QUALIFYING: TargetPolicy(
        version=TARGET_POLICY_VERSION,
        horizon=ForecastHorizon.POST_QUALIFYING,
        information_cutoff=(
            "The verified final qualifying classification and grid are available "
            "for every intended race entry, including published penalties."
        ),
        prediction_deadline=(
            "Publish after qualifying verification and before the race start. A "
            "sprint does not move this cutoff: sprint and Grand Prix are "
            "distinct sessions."
        ),
        target=(
            "Officially classified race finishing order, normalized to contiguous "
            "internal ranks only for target-eligible classified entrants."
        ),
        excluded_result_statuses=("dns", "dsq", "unknown"),
    ),
}


def target_policy(horizon: ForecastHorizon | str) -> TargetPolicy:
    """Return the current policy; callers persist its version with every run."""
    return _POLICIES[ForecastHorizon(horizon)]
