"""Pure feature and target construction for the fixed WP09 baselines."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd
from gridoracle.domain.results import classify_result

from pipeline.dataset.historical import DatasetBackfill
from pipeline.issuance.domain import positive_int

PRE_WEEKEND, POST_QUALIFYING = "pre_weekend", "post_qualifying"


def race_standings(
    races: Iterable[Mapping[str, Any]],
    season: int,
    round_number: int,
    drivers: Iterable[str],
) -> dict[str, int]:
    """Race-only standings before `round_number`, as the WP05 dataset ranks them.

    Only Grand Prix `Results` count (sprint points are not inferred). Rows from
    this round or later are ignored, whatever the provider has published.
    """
    rows = [
        {
            "season": season,
            "round": int(race["round"]),
            "driver": str(row["Driver"]["driverId"]),
            "points": float(row.get("points", 0) or 0),
        }
        for race in races
        if int(race["season"]) == season and int(race["round"]) < round_number
        for row in race.get("Results", [])
    ]
    targets = sorted(set(drivers))
    rows += [{"season": season, "round": round_number, "driver": driver, "points": 0.0} for driver in targets]
    frame = pd.DataFrame(rows)
    ranks = DatasetBackfill._standings(frame, "driver")
    current = frame["round"] == round_number
    return dict(zip(frame.loc[current, "driver"], ranks[current], strict=True))


def feature_records(
    *,
    season: int,
    round_number: int,
    horizon: str,
    cutoff: str,
    entries: Iterable[Mapping[str, Any]],
    standings: Mapping[str, int],
    qualifying: Mapping[str, int] | None = None,
) -> list[dict[str, Any]]:
    """One row per active entry, keyed by the stable event-entry identity."""
    records = []
    for entry in sorted(entries, key=lambda item: item["key"]):
        row = {
            "race_key": f"{season}/{round_number}",
            "driver_identity_key": entry["key"],
            "constructor_identity_key": entry["team_key"],
            "horizon": horizon,
            "cutoff": cutoff,
            "entry_provenance": entry["provenance"],
            "driver_championship_position_race_only": int(standings[entry["driver"]]),
            "missing__qualifying": True,
        }
        if horizon == POST_QUALIFYING:
            position = (qualifying or {}).get(entry["driver"])
            row["qualifying_position"] = position
            row["missing__qualifying"] = position is None
        records.append(row)
    return records


def qualifying_positions(race: Mapping[str, Any]) -> dict[str, int]:
    positions = {}
    for row in race.get("QualifyingResults", []):
        position = positive_int(row.get("position"))
        if position is not None:
            positions[str(row["Driver"]["driverId"])] = position
    return positions


def qualifying_verified(race: Mapping[str, Any]) -> bool:
    """Every classified position is present once, from 1 without gaps."""
    rows = race.get("QualifyingResults", [])
    positions = sorted(positive_int(row.get("position")) or 0 for row in rows)
    return bool(rows) and positions == list(range(1, len(rows) + 1))


def targets(field: Mapping[str, str], race: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """WP06 targets for a forecast field: entry key -> provider driver id.

    Official classified ranks are made contiguous over the field's eligible
    rows (the contract's internal rank). A field entry without a result is a
    non-starter; a classified driver outside the field is counted, not scored.
    """
    results = {str(row["Driver"]["driverId"]): row for row in race.get("Results", [])}
    eligible = []
    rows = {}
    for key, driver in field.items():
        row = results.get(driver)
        if row is None:
            rows[key] = None
            continue
        status = classify_result(row.get("status"), positive_int(row.get("positionText")))
        rows[key] = None
        if status.is_target_eligible:
            eligible.append((status.official_rank, key))
    for internal, (_, key) in enumerate(sorted(eligible), start=1):
        rows[key] = internal
    outside = len(set(results) - set(field.values()))
    return [{"driver": key, "rank": rows[key]} for key in sorted(rows)], outside
