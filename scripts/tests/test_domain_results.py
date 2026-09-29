import pytest

from gridoracle.domain.results import (
    CanonicalResultStatus,
    classify_result,
    rankable_target_rows,
)


@pytest.mark.parametrize(
    ("raw_status", "official_rank", "expected", "eligible"),
    [
        ("Finished", 1, CanonicalResultStatus.FINISHED, True),
        ("Lapped", 12, CanonicalResultStatus.LAPPED, True),
        ("+1 Lap", 13, CanonicalResultStatus.LAPPED, True),
        ("Retired", 14, CanonicalResultStatus.CLASSIFIED_RETIREMENT, True),
        ("Retired", None, CanonicalResultStatus.RETIRED_UNCLASSIFIED, False),
        ("DNS", None, CanonicalResultStatus.DNS, False),
        ("DSQ", None, CanonicalResultStatus.DSQ, False),
        ("provider-new-status", 15, CanonicalResultStatus.UNKNOWN, False),
    ],
)
def test_provider_status_target_policy(raw_status, official_rank, expected, eligible):
    result = classify_result(raw_status, official_rank)
    assert result.canonical_status == expected
    assert result.is_target_eligible is eligible


def test_internal_rank_is_contiguous_and_preserves_official_rank():
    rows = rankable_target_rows(
        [
            classify_result("Finished", 1),
            classify_result("DNS", None),
            classify_result("+1 Lap", 3),
            classify_result("Retired", 4),
            classify_result("DSQ", 2),
        ]
    )
    assert [row.official_rank for row in rows] == [1, None, 3, 4, 2]
    assert [row.internal_rank for row in rows] == [1, None, 2, 3, None]


def test_duplicate_official_target_rank_blocks_scoring():
    with pytest.raises(ValueError, match="official ranks"):
        rankable_target_rows(
            [classify_result("Finished", 1), classify_result("Lapped", 1)]
        )
