from gridoracle.domain.identity import LegacyIdentity, build_legacy_identity_report


def test_legacy_identity_report_does_not_auto_merge_ambiguous_names():
    report = build_legacy_identity_report(
        [
            LegacyIdentity("team", 1, "Alpha Racing", None),
            LegacyIdentity("team", 2, "alpha racing", None),
            LegacyIdentity("circuit", 4, None, "circuit:known"),
        ]
    )
    assert report["assignments"][0]["identity_key"] == "circuit:known"
    assert report["assignments"][1]["identity_key"] == "legacy:team:1"
    assert report["unresolved"] == [
        {
            "entity_kind": "circuit",
            "legacy_identifier": "4",
            "reason": "missing_display_name",
        },
        {
            "entity_kind": "team",
            "legacy_identifier": "alpha racing",
            "reason": "ambiguous_display_name",
            "legacy_ids": [1, 2],
        },
    ]
