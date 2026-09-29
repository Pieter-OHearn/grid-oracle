"""Provider-status normalization and ranking-label eligibility.

Provider status strings remain raw provenance.  This module maps only their
meaning into a small stable vocabulary; it never rewrites official results.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class CanonicalResultStatus(StrEnum):
    FINISHED = "finished"
    LAPPED = "lapped"
    CLASSIFIED_RETIREMENT = "classified_retirement"
    RETIRED_UNCLASSIFIED = "retired_unclassified"
    DNS = "dns"
    DSQ = "dsq"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ResultClassification:
    """Raw provider fact, official presentation rank, and internal target rank."""

    raw_status: str | None
    canonical_status: CanonicalResultStatus
    official_rank: int | None
    internal_rank: int | None = None

    @property
    def is_target_eligible(self) -> bool:
        return (
            self.canonical_status
            in {
                CanonicalResultStatus.FINISHED,
                CanonicalResultStatus.LAPPED,
                CanonicalResultStatus.CLASSIFIED_RETIREMENT,
            }
            and self.official_rank is not None
        )


_DNS = {"dns", "did not start", "not started", "withdrawn", "withdrew"}
_DSQ = {"dsq", "disqualified", "excluded"}
_RETIRED = {"retired", "ret", "dnf", "did not finish", "accident", "engine"}
_UNINTERPRETABLE = {
    "not classified",
    "107% rule",
    "did not qualify",
    "not qualified",
    "did not prequalify",
    "unknown",
}


def classify_result(
    raw_status: str | None, official_rank: int | None
) -> ResultClassification:
    """Map a provider result without guessing a missing official classification.

    `+1 Lap` and equivalent historical forms are lapped classified finishes. A
    retirement with a positive official rank is a *classified retirement*;
    absent that rank it remains visible but cannot silently enter a label.
    """
    normalized = (raw_status or "").strip().casefold()
    if normalized in _DNS:
        status = CanonicalResultStatus.DNS
    elif normalized in _DSQ:
        status = CanonicalResultStatus.DSQ
    elif normalized == "finished":
        status = CanonicalResultStatus.FINISHED
    elif "lap" in normalized or normalized.startswith("+"):
        status = CanonicalResultStatus.LAPPED
    elif normalized in _UNINTERPRETABLE or not normalized:
        status = CanonicalResultStatus.UNKNOWN
    elif normalized in _RETIRED:
        status = (
            CanonicalResultStatus.CLASSIFIED_RETIREMENT
            if official_rank is not None
            else CanonicalResultStatus.RETIRED_UNCLASSIFIED
        )
    else:
        # Ergast/FastF1 often records a mechanical or incident reason rather
        # than the literal word "Retired". A positive official classification
        # is authoritative, so preserve it as a classified retirement; an
        # unranked non-finish stays visible but cannot become a target label.
        status = (
            CanonicalResultStatus.CLASSIFIED_RETIREMENT
            if official_rank is not None
            else CanonicalResultStatus.RETIRED_UNCLASSIFIED
        )
    return ResultClassification(raw_status, status, official_rank)


def rankable_target_rows(
    rows: Iterable[ResultClassification],
) -> list[ResultClassification]:
    """Attach contiguous internal ranks while preserving official ranks exactly.

    An official rank is authoritative presentation/scoring evidence.  Internal
    rank is a derived model label: the target-eligible rows are ordered by the
    official rank and must be unique.  DNS, DSQ and unknown rows are returned
    unranked so a caller can report their exclusion instead of treating null as
    a DNF.
    """
    materialized = list(rows)
    eligible = [row for row in materialized if row.is_target_eligible]
    ranks = [row.official_rank for row in eligible]
    if len(ranks) != len(set(ranks)):
        raise ValueError("official ranks must be unique before deriving target ranks")

    by_object_id = {
        id(row): ResultClassification(
            raw_status=row.raw_status,
            canonical_status=row.canonical_status,
            official_rank=row.official_rank,
            internal_rank=index,
        )
        for index, row in enumerate(
            sorted(eligible, key=lambda item: item.official_rank or 0), start=1
        )
    }
    return [by_object_id.get(id(row), row) for row in materialized]
