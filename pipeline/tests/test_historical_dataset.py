"""Acceptance tests for WP05's audited historical dataset contract."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from pipeline.dataset.historical import (
    AVAILABILITY_ARCHIVED_UNKNOWN_AS_OF,
    DatasetBackfill,
    FeatureHorizon,
    RawSnapshot,
)


def _race(round_number: int, results: list[tuple[str, str, int, float, str]], *, season: int = 2024) -> dict:
    return {
        "season": str(season),
        "round": str(round_number),
        "raceName": f"Example {round_number}",
        "date": f"2024-0{round_number}-01",
        "time": "12:00:00Z",
        "Results": [
            {
                "position": str(position),
                "positionText": str(position) if status in {"Finished", "Lapped"} else "R",
                "points": str(points),
                "status": status,
                "Driver": {"driverId": driver},
                "Constructor": {"constructorId": constructor},
            }
            for driver, constructor, position, points, status in results
        ],
    }


def _qualifying(round_number: int, positions: list[tuple[str, str, int]], *, season: int = 2024) -> dict:
    return {
        "season": str(season),
        "round": str(round_number),
        "raceName": f"Example {round_number}",
        "date": f"2024-0{round_number}-01",
        "time": "12:00:00Z",
        "QualifyingResults": [
            {
                "position": str(position),
                "Driver": {"driverId": driver},
                "Constructor": {"constructorId": constructor},
            }
            for driver, constructor, position in positions
        ],
    }


def _snapshot(name: str, races: list[dict]) -> RawSnapshot:
    return RawSnapshot(
        name=name,
        provider="jolpica",
        payload=json.dumps({"MRData": {"RaceTable": {"Races": races}}}).encode(),
        retrieved_at=datetime(2026, 9, 28, tzinfo=UTC),
    )


def _backfill(*, reversed_entries: bool = False, include_future: bool = False) -> DatasetBackfill:
    rounds = [
        _race(1, [("a", "team", 1, 25, "Finished"), ("b", "team", 3, 15, "Lapped")]),
        _race(2, [("a", "team", 2, 18, "Finished"), ("b", "team", 4, 12, "Retired")]),
    ]
    qualifying = [
        _qualifying(1, [("a", "team", 1), ("b", "team", 2)]),
        _qualifying(2, [("a", "team", 2), ("b", "team", 1)]),
    ]
    if include_future:
        rounds.append(_race(3, [("a", "team", 20, 0, "Retired"), ("b", "team", 1, 25, "Finished")]))
        qualifying.append(_qualifying(3, [("a", "team", 2), ("b", "team", 1)]))
    if reversed_entries:
        for race in rounds:
            race["Results"].reverse()
        for race in qualifying:
            race["QualifyingResults"].reverse()
    return DatasetBackfill([_snapshot("2024-results-0.json", rounds), _snapshot("2024-qualifying-0.json", qualifying)])


def test_future_fact_cannot_alter_an_earlier_feature_snapshot():
    baseline, _ = _backfill().build()
    with_future, _ = _backfill(include_future=True).build()
    before = baseline[(baseline["round"] == 2) & (baseline["horizon"] == "pre_weekend")]
    after = with_future[(with_future["round"] == 2) & (with_future["horizon"] == "pre_weekend")]
    pd.testing.assert_frame_equal(before.reset_index(drop=True), after.reset_index(drop=True))


def test_qualifying_never_appears_in_pre_weekend_features():
    backfill = _backfill()
    features, _ = backfill.build()
    pre = backfill.features_for_horizon(features, FeatureHorizon.PRE_WEEKEND)
    assert "qualifying_position" not in pre.columns
    assert "qualifying_normalized_position" not in pre.columns
    assert pre["missing__qualifying"].all()


def test_same_raw_snapshots_reconstruct_identical_features_and_manifest(tmp_path: Path):
    first = _backfill().write(tmp_path / "one")
    second = _backfill().write(tmp_path / "two")
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert [row["parquet_sha256"] for row in first["outputs"]] == [row["parquet_sha256"] for row in second["outputs"]]


def test_entrant_order_cannot_change_feature_values():
    normal, _ = _backfill().build()
    reversed_order, _ = _backfill(reversed_entries=True).build()
    pd.testing.assert_frame_equal(normal, reversed_order)


def test_constructor_last_three_is_aggregated_by_race_not_by_car():
    backfill = DatasetBackfill(
        [
            _snapshot(
                "2024-results-0.json",
                [
                    _race(1, [("a", "team", 1, 25, "Finished"), ("b", "team", 3, 15, "Finished")]),
                    _race(2, [("a", "team", 2, 18, "Finished"), ("b", "team", 4, 12, "Finished")]),
                    _race(3, [("a", "team", 3, 15, "Finished"), ("b", "team", 5, 10, "Finished")]),
                ],
            )
        ]
    )
    features, _ = backfill.build()
    feature = features[
        (features["round"] == 3)
        & (features["driver_identity_key"] == "provider:jolpica:driver:a")
        & (features["horizon"] == "pre_weekend")
    ].iloc[0]
    # Per-race constructor means are 2.0 then 3.0, so the value is 2.5.
    assert feature["constructor_finish_mean_last_3"] == 2.5


def test_unclassified_position_text_cannot_become_a_finish_feature():
    results, _, _ = _backfill()._reconcile()
    retired = results[(results["driver_provider_id"] == "b") & (results["round"] == 2)].iloc[0]
    assert pd.isna(retired["finish_position"])
    assert not retired["target_eligible"]
    assert retired["canonical_status"] == "retired_unclassified"


def test_conflicting_identity_is_quarantined_even_when_a_third_page_arrives():
    first = _race(1, [("a", "team", 1, 25, "Finished")])
    second = _race(1, [("a", "team", 2, 18, "Finished")])
    third = _race(1, [("a", "team", 3, 15, "Finished")])
    backfill = DatasetBackfill(
        [
            _snapshot("2024-results-0.json", [first]),
            _snapshot("2024-results-1.json", [second]),
            _snapshot("2024-results-2.json", [third]),
        ]
    )
    results, _, report = backfill._reconcile()
    assert results.empty
    assert len(report["identity_conflicts"]) == 1


def test_standings_use_competition_ranks_for_equal_points():
    rounds = [
        _race(1, [("a", "team", 1, 0, "Finished"), ("b", "team", 2, 0, "Finished")]),
        _race(2, [("a", "team", 1, 25, "Finished"), ("b", "team", 2, 18, "Finished")]),
    ]
    features, _ = DatasetBackfill([_snapshot("2024-results-0.json", rounds)]).build()
    standings = features[(features["round"] == 2) & (features["horizon"] == "pre_weekend")]
    assert set(standings["driver_championship_position_race_only"]) == {1}


def test_partial_season_runs_finish_one_immutable_manifest(tmp_path: Path):
    races = [
        _race(1, [("a", "team", 1, 25, "Finished")], season=2023),
        _race(1, [("a", "team", 1, 25, "Finished")], season=2024),
    ]
    qualifying = [
        _qualifying(1, [("a", "team", 1)], season=2023),
        _qualifying(1, [("a", "team", 1)], season=2024),
    ]
    backfill = DatasetBackfill(
        [_snapshot("mixed-results-0.json", races), _snapshot("mixed-qualifying-0.json", qualifying)]
    )
    first = backfill.write(tmp_path, seasons=[2023])
    assert not first["complete"]
    assert first["manifest_sha256"] is None
    second = backfill.write(tmp_path, seasons=[2024])
    assert second["complete"]
    resumed = backfill.write(tmp_path)
    assert resumed["manifest_sha256"] == second["manifest_sha256"]


def test_checkpoint_reuse_verifies_the_fresh_feature_frame_and_contract(tmp_path: Path):
    backfill = _backfill()
    result = backfill.write(tmp_path)
    checkpoint = next(Path(result["root"]).glob("**/*.checkpoint.json"))
    payload = json.loads(checkpoint.read_text())
    payload["feature_frame_sha256"] = "stale"
    checkpoint.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="checkpoint mismatch"):
        backfill.write(tmp_path)


def test_archive_source_status_fixture_covers_real_downloaded_records(tmp_path: Path):
    fixture = json.loads((Path(__file__).parent / "fixtures" / "wp05-source-status.json").read_text())
    backfill = DatasetBackfill.from_jolpica_archive(Path(fixture["archive"]))
    manifest = backfill.source_manifest()
    assert len(manifest) == fixture["real_record_count"]
    assert {row["availability_quality"] for row in manifest} == {fixture["availability_quality"]}
    reconstructed = backfill.write(tmp_path / "source-fixture")
    assert reconstructed["source_manifest_sha256"] == fixture["source_manifest_sha256"]
    assert reconstructed["manifest_sha256"] == fixture["dataset_manifest_sha256"]
    committed = json.loads(
        Path("docs/datasets/versions/dataset-2026.2-wp05-87d0a99ef821-9f459a82d698/manifest.json").read_text()
    )
    assert committed["source_snapshots"] == manifest
    assert committed["source_manifest_sha256"] == fixture["source_manifest_sha256"]


def test_report_and_manifest_are_reconstructible_from_raw_snapshots(tmp_path: Path):
    result = _backfill().write(tmp_path)
    report = result["audit"]
    assert {"races", "entries", "sessions", "duplicates", "nulls", "exclusions", "identity_conflicts"} <= set(report)
    assert report["exclusions"]["weather"] == "weather-free cohort; no weather snapshot is included"
    assert result["dataset_quality"] == AVAILABILITY_ARCHIVED_UNKNOWN_AS_OF
    for output in result["outputs"]:
        path = Path(result["root"]) / output["path"]
        assert path.exists()
        assert path.with_suffix(".checkpoint.json").exists()
