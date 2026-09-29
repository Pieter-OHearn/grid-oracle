# ruff: noqa: E501
"""Point-in-time-safe reconstruction from immutable provider snapshots.

This module intentionally distinguishes chronological facts from facts proven
available at a historical cutoff.  An archive retrieved after a race can be
used to reconstruct a *chronologically isolated* feature view, but it is not
evidence that the provider had published that fact when a forecast was due.
That distinction is carried in every row and manifest rather than hidden in a
loader timestamp.
"""

from __future__ import annotations

import json
import tarfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd
from gridoracle.domain.results import CanonicalResultStatus, classify_result

AVAILABILITY_ARCHIVED_UNKNOWN_AS_OF = "archived_retrieval_known_asof_unknown"
DATASET_CONTRACT_VERSION = "2026.1-wp05"


class FeatureHorizon(StrEnum):
    PRE_WEEKEND = "pre_weekend"
    POST_QUALIFYING = "post_qualifying"


@dataclass(frozen=True)
class RawSnapshot:
    """An immutable raw response and only the timestamps actually known for it."""

    name: str
    provider: str
    payload: bytes
    retrieved_at: datetime | None
    source_available_at: datetime | None = None

    @property
    def sha256(self) -> str:
        return sha256(self.payload).hexdigest()

    @property
    def availability_quality(self) -> str:
        if self.source_available_at is not None:
            return "source_available_at_verified"
        if self.retrieved_at is not None:
            return AVAILABILITY_ARCHIVED_UNKNOWN_AS_OF
        return "retrieval_timestamp_unknown"

    def parsed(self) -> Mapping[str, Any]:
        value = json.loads(self.payload)
        if not isinstance(value, dict):
            raise ValueError(f"snapshot {self.name} is not a JSON object")
        return value


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    tier: str
    horizons: tuple[FeatureHorizon, ...]
    description: str
    source: str
    enabled: bool = True


class FeatureRegistry:
    """A horizon gate, not just a documentation list.

    A missing registry entry is rejected.  This stops an accidental qualifying
    column from being slipped into a pre-weekend feature frame.
    """

    def __init__(self, definitions: Iterable[FeatureDefinition]):
        self._definitions = {definition.name: definition for definition in definitions}

    @classmethod
    def audited_default(cls) -> "FeatureRegistry":
        both = (FeatureHorizon.PRE_WEEKEND, FeatureHorizon.POST_QUALIFYING)
        post = (FeatureHorizon.POST_QUALIFYING,)
        return cls(
            (
                FeatureDefinition(
                    "driver_finish_mean_last_3",
                    "recency",
                    both,
                    "Mean classified finish across the driver's preceding three Grands Prix.",
                    "race results",
                ),
                FeatureDefinition(
                    "constructor_finish_mean_last_3",
                    "recency",
                    both,
                    "Mean of the constructor's per-race means across its preceding three Grands Prix.",
                    "race results",
                ),
                FeatureDefinition(
                    "driver_recency_races",
                    "recency",
                    both,
                    "Number of earlier Grand Prix result records for the driver.",
                    "race results",
                ),
                FeatureDefinition(
                    "constructor_recency_races",
                    "recency",
                    both,
                    "Number of earlier constructor Grand Prix appearances.",
                    "race results",
                ),
                FeatureDefinition(
                    "driver_reliability_rate_last_3",
                    "reliability",
                    both,
                    "Share of the preceding three results recorded as finished or lapped.",
                    "race results",
                ),
                FeatureDefinition(
                    "driver_championship_position_race_only",
                    "recency",
                    both,
                    "Race-result-only championship rank before this Grand Prix; sprint points are not inferred.",
                    "race results",
                ),
                FeatureDefinition(
                    "constructor_championship_position_race_only",
                    "recency",
                    both,
                    "Race-result-only constructor rank before this Grand Prix; sprint points are not inferred.",
                    "race results",
                ),
                FeatureDefinition(
                    "qualifying_normalized_position",
                    "normalized_pace",
                    post,
                    "Current qualifying position divided by reconciled field size.",
                    "qualifying results",
                ),
                FeatureDefinition(
                    "qualifying_position",
                    "normalized_pace",
                    post,
                    "Current Grand Prix qualifying position; not a final-grid proxy.",
                    "qualifying results",
                ),
                FeatureDefinition(
                    "missing__qualifying",
                    "missingness",
                    both,
                    "Explicit flag for unavailable qualifying data.",
                    "qualifying results",
                ),
                FeatureDefinition(
                    "missing__history",
                    "missingness",
                    both,
                    "Explicit flag for no preceding classified result history.",
                    "race results",
                ),
            )
        )

    def enabled_for(self, horizon: FeatureHorizon) -> list[FeatureDefinition]:
        return [
            definition
            for definition in self._definitions.values()
            if definition.enabled and horizon in definition.horizons
        ]

    def validate_columns(self, frame: pd.DataFrame, horizon: FeatureHorizon) -> None:
        allowed = {definition.name for definition in self.enabled_for(horizon)}
        reserved = {
            "season",
            "round",
            "race_key",
            "driver_identity_key",
            "constructor_identity_key",
            "horizon",
            "cutoff",
            "availability_quality",
            "asof_eligible",
            "entry_provenance",
        }
        unexpected = set(frame.columns) - allowed - reserved
        if unexpected:
            raise ValueError(f"unregistered feature columns for {horizon}: {sorted(unexpected)}")
        disallowed = {
            definition.name for definition in self._definitions.values() if horizon not in definition.horizons
        }
        present = disallowed & set(frame.columns)
        if present:
            raise ValueError(f"features forbidden at {horizon}: {sorted(present)}")

    def dictionary(self) -> list[dict[str, object]]:
        return [
            {
                "name": definition.name,
                "tier": definition.tier,
                "horizons": [horizon.value for horizon in definition.horizons],
                "description": definition.description,
                "source": definition.source,
                "enabled": definition.enabled,
            }
            for definition in sorted(self._definitions.values(), key=lambda item: item.name)
        ]


def _event_time(race: Mapping[str, Any]) -> datetime:
    date = str(race["date"])
    time = str(race.get("time", "00:00:00Z"))
    return datetime.fromisoformat(f"{date}T{time}".replace("Z", "+00:00")).astimezone(UTC)


def _identity(kind: str, provider_id: str) -> str:
    # A provider-scoped identity is deliberately not name merged.  A future
    # curated WP02 alias map can replace it without rewriting raw evidence.
    return f"provider:jolpica:{kind}:{provider_id}"


def _positive_int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item),
    ).encode()


class DatasetBackfill:
    """Resumable season/session backfill with deterministic reconciliation.

    Progress is an append-only checkpoint file per season and session.  A
    completed checkpoint is reused only when the exact source-snapshot digest
    list is unchanged; a changed archive produces a new versioned dataset.
    """

    def __init__(
        self,
        snapshots: Iterable[RawSnapshot],
        *,
        registry: FeatureRegistry | None = None,
        contract_version: str = DATASET_CONTRACT_VERSION,
    ):
        self.snapshots = tuple(sorted(snapshots, key=lambda snapshot: snapshot.name))
        self.registry = registry or FeatureRegistry.audited_default()
        self.contract_version = contract_version

    @classmethod
    def from_jolpica_archive(cls, archive: Path) -> "DatasetBackfill":
        """Load the committed real-record archive without fabricating as-of times."""
        summary_path = archive.parent / "baseline-summary.json"
        summary = json.loads(summary_path.read_text())
        retrieved_at = datetime.fromisoformat(summary["retrieved_at"])
        snapshots: list[RawSnapshot] = []
        with tarfile.open(archive, "r:gz") as contents:
            for member in sorted(contents.getmembers(), key=lambda item: item.name):
                if not member.isfile() or not member.name.endswith(".json") or Path(member.name).name.startswith("._"):
                    continue
                source = contents.extractfile(member)
                assert source is not None
                snapshots.append(
                    RawSnapshot(
                        name=Path(member.name).name,
                        provider="jolpica",
                        payload=source.read(),
                        retrieved_at=retrieved_at,
                    )
                )
        return cls(snapshots)

    def source_manifest(self) -> list[dict[str, object]]:
        return [
            {
                "name": snapshot.name,
                "provider": snapshot.provider,
                "sha256": snapshot.sha256,
                "retrieved_at": snapshot.retrieved_at.isoformat() if snapshot.retrieved_at else None,
                "source_available_at": snapshot.source_available_at.isoformat()
                if snapshot.source_available_at
                else None,
                "availability_quality": snapshot.availability_quality,
            }
            for snapshot in self.snapshots
        ]

    def _reconcile(self) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
        """Merge paginated results/qualifying records by provider identity.

        An exact repeated row is counted as a duplicate.  A conflicting repeated
        row is retained in the audit report and excluded from feature output.
        """
        results: dict[tuple[int, int, str], dict[str, object]] = {}
        qualifying: dict[tuple[int, int, str], dict[str, object]] = {}
        duplicates: Counter[str] = Counter()
        conflicts: list[dict[str, object]] = []
        sessions: Counter[str] = Counter()
        for snapshot in self.snapshots:
            payload = snapshot.parsed()
            races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
            if not isinstance(races, list):
                raise ValueError(f"snapshot {snapshot.name} has no race list")
            kind = "qualifying" if "qualifying" in snapshot.name else "results"
            for race in races:
                season, round_number = int(race["season"]), int(race["round"])
                rows = race.get("QualifyingResults" if kind == "qualifying" else "Results", [])
                sessions[f"{season}:{round_number}:{kind}"] += 1
                for row in rows:
                    driver_id = str(row["Driver"]["driverId"])
                    constructor_id = str(row["Constructor"]["constructorId"])
                    key = (season, round_number, driver_id)
                    record = {
                        "season": season,
                        "round": round_number,
                        "race_key": f"{season}:{round_number}",
                        "race_name": race["raceName"],
                        "event_at": _event_time(race),
                        "driver_identity_key": _identity("driver", driver_id),
                        "constructor_identity_key": _identity("constructor", constructor_id),
                        "driver_provider_id": driver_id,
                        "constructor_provider_id": constructor_id,
                        "snapshot_sha256": snapshot.sha256,
                        "availability_quality": snapshot.availability_quality,
                        "source_available_at": snapshot.source_available_at,
                        "retrieved_at": snapshot.retrieved_at,
                    }
                    if kind == "results":
                        official_rank = _positive_int(row.get("position"))
                        status = str(row.get("status", ""))
                        classification = classify_result(status, official_rank)
                        record.update(
                            finish_position=official_rank,
                            points=float(row.get("points", 0)),
                            raw_status=status,
                            target_eligible=classification.is_target_eligible,
                            canonical_status=classification.canonical_status.value,
                        )
                        target = results
                    else:
                        record.update(qualifying_position=_positive_int(row.get("position")))
                        target = qualifying
                    prior = target.get(key)
                    if prior is None:
                        target[key] = record
                    elif _canonical_json(
                        {field: value for field, value in prior.items() if field != "snapshot_sha256"}
                    ) == _canonical_json(
                        {field: value for field, value in record.items() if field != "snapshot_sha256"}
                    ):
                        duplicates[kind] += 1
                    else:
                        conflicts.append(
                            {
                                "kind": kind,
                                "race_key": f"{season}:{round_number}",
                                "driver_provider_id": driver_id,
                                "reason": "conflicting_duplicate_provider_identity",
                            }
                        )
                        target.pop(key, None)
        report = {
            "duplicates": dict(sorted(duplicates.items())),
            "identity_conflicts": sorted(conflicts, key=lambda item: _canonical_json(item)),
            "sessions": {
                "result_sessions": len({key.rsplit(":", 1)[0] for key in sessions if key.endswith(":results")}),
                "qualifying_sessions": len({key.rsplit(":", 1)[0] for key in sessions if key.endswith(":qualifying")}),
                "source_page_observations": dict(sorted(sessions.items())),
            },
        }
        return (
            pd.DataFrame(
                sorted(results.values(), key=lambda row: (row["season"], row["round"], row["driver_provider_id"]))
            ),
            pd.DataFrame(
                sorted(qualifying.values(), key=lambda row: (row["season"], row["round"], row["driver_provider_id"]))
            ),
            report,
        )

    @staticmethod
    def _standings(frame: pd.DataFrame, key: str) -> pd.Series:
        values: dict[tuple[int, int, str], int] = {}
        for season, season_rows in frame.groupby("season", sort=True):
            totals: defaultdict[str, float] = defaultdict(float)
            for round_number, event_rows in season_rows.groupby("round", sort=True):
                ranks = {
                    entity: position
                    for position, entity in enumerate(sorted(totals, key=lambda item: (-totals[item], item)), start=1)
                }
                for entity in event_rows[key]:
                    values[(int(season), int(round_number), str(entity))] = ranks.get(
                        entity, len(ranks) + 1 if ranks else 1
                    )
                for entity, points in event_rows.groupby(key, sort=True)["points"].sum().items():
                    totals[str(entity)] += float(points)
        return pd.Series(
            [values[(int(row.season), int(row.round), str(getattr(row, key)))] for row in frame.itertuples()],
            index=frame.index,
            dtype="int64",
        )

    def _features(self, results: pd.DataFrame, qualifying: pd.DataFrame) -> pd.DataFrame:
        if results.empty:
            return pd.DataFrame()
        rows = results.copy().sort_values(["season", "round", "driver_identity_key"], kind="stable")
        rows["race_order"] = pd.factorize(rows["race_key"], sort=True)[0]
        classified = rows["finish_position"].where(rows["target_eligible"])
        rows["driver_finish_mean_last_3"] = classified.groupby(rows["driver_identity_key"], sort=False).transform(
            lambda item: item.shift().rolling(3, min_periods=1).mean()
        )
        rows["driver_recency_races"] = rows.groupby("driver_identity_key", sort=False).cumcount()
        reliable = (
            rows["canonical_status"]
            .isin({CanonicalResultStatus.FINISHED.value, CanonicalResultStatus.LAPPED.value})
            .astype(float)
        )
        rows["driver_reliability_rate_last_3"] = reliable.groupby(rows["driver_identity_key"], sort=False).transform(
            lambda item: item.shift().rolling(3, min_periods=1).mean()
        )

        constructor_race = (
            rows.assign(classified_finish=classified)
            .groupby(["season", "round", "constructor_identity_key"], as_index=False, sort=True)
            .agg(constructor_finish=("classified_finish", "mean"), constructor_points=("points", "sum"))
        )
        constructor_race["constructor_finish_mean_last_3"] = constructor_race.groupby(
            "constructor_identity_key", sort=False
        )["constructor_finish"].transform(lambda item: item.shift().rolling(3, min_periods=1).mean())
        constructor_race["constructor_recency_races"] = constructor_race.groupby(
            "constructor_identity_key", sort=False
        ).cumcount()
        rows = rows.merge(
            constructor_race[
                [
                    "season",
                    "round",
                    "constructor_identity_key",
                    "constructor_finish_mean_last_3",
                    "constructor_recency_races",
                ]
            ],
            on=["season", "round", "constructor_identity_key"],
            how="left",
            validate="many_to_one",
        )
        rows["driver_championship_position_race_only"] = self._standings(rows, "driver_identity_key")
        rows["constructor_championship_position_race_only"] = self._standings(rows, "constructor_identity_key")

        qualifying_rows = qualifying.reindex(
            columns=["season", "round", "driver_identity_key", "qualifying_position"]
        ).copy()
        field_sizes = qualifying_rows.groupby(["season", "round"])["driver_identity_key"].transform("nunique")
        qualifying_rows["qualifying_normalized_position"] = qualifying_rows["qualifying_position"] / field_sizes
        joined = rows.merge(
            qualifying_rows,
            on=["season", "round", "driver_identity_key"],
            how="left",
            validate="one_to_one",
        )
        output: list[pd.DataFrame] = []
        common = [
            "season",
            "round",
            "race_key",
            "driver_identity_key",
            "constructor_identity_key",
            "availability_quality",
        ]
        pre = joined[
            [
                *common,
                "driver_finish_mean_last_3",
                "constructor_finish_mean_last_3",
                "driver_recency_races",
                "constructor_recency_races",
                "driver_reliability_rate_last_3",
                "driver_championship_position_race_only",
                "constructor_championship_position_race_only",
            ]
        ].copy()
        pre["horizon"] = FeatureHorizon.PRE_WEEKEND.value
        pre["cutoff"] = "before_first_competitive_session"
        pre["asof_eligible"] = False
        pre["entry_provenance"] = "reconstructed_from_result_entry"
        pre["missing__qualifying"] = True
        pre["missing__history"] = pre["driver_finish_mean_last_3"].isna()
        output.append(pre)
        post = joined.copy()
        post["horizon"] = FeatureHorizon.POST_QUALIFYING.value
        post["cutoff"] = "after_verified_qualifying_before_race"
        post["asof_eligible"] = False
        post["entry_provenance"] = "reconstructed_from_result_entry"
        post["missing__qualifying"] = post["qualifying_position"].isna()
        post["missing__history"] = post["driver_finish_mean_last_3"].isna()
        output.append(
            post[
                [
                    *pre.columns.tolist(),
                    "qualifying_position",
                    "qualifying_normalized_position",
                ]
            ]
        )
        combined = (
            pd.concat(output, ignore_index=True)
            .sort_values(["season", "round", "horizon", "driver_identity_key"], kind="stable")
            .reset_index(drop=True)
        )
        return combined

    def features_for_horizon(self, features: pd.DataFrame, horizon: FeatureHorizon) -> pd.DataFrame:
        """Return a structural horizon view, removing forbidden columns entirely."""
        forbidden = {
            definition.name for definition in self.registry._definitions.values() if horizon not in definition.horizons
        }
        frame = features[features["horizon"] == horizon.value].drop(columns=forbidden, errors="ignore")
        self.registry.validate_columns(frame, horizon)
        return frame

    def build(self) -> tuple[pd.DataFrame, dict[str, object]]:
        results, qualifying, audit = self._reconcile()
        features = self._features(results, qualifying)
        nulls = {column: int(value) for column, value in features.isna().sum().sort_index().items() if value}
        audit.update(
            {
                "races": int(results["race_key"].nunique()) if not results.empty else 0,
                "entries": int(len(results)),
                "qualifying_entries": int(len(qualifying)),
                "feature_rows": int(len(features)),
                "nulls": nulls,
                "exclusions": {
                    "asof_evaluation": "all archived rows are marked asof_eligible=false because source_available_at is unknown",
                    "sprint_points": "not present in the archived source; standings are explicitly race-only",
                    "weather": "weather-free cohort; no weather snapshot is included",
                    "degradation_compound_proxies": "not registered pending an ablation",
                },
            }
        )
        return features, audit

    def write(self, root: Path, *, seasons: Iterable[int] | None = None) -> dict[str, object]:
        """Write versioned Parquet, checkpoints and an immutable manifest.

        ``seasons`` permits resumable backfills.  Completed season/session
        checkpoint data is content-addressed by the source snapshot manifest.
        """
        features, report = self.build()
        selected = set(seasons) if seasons is not None else set(features["season"].unique())
        source_manifest = self.source_manifest()
        source_hash = sha256(_canonical_json(source_manifest)).hexdigest()
        root = root / f"dataset-{self.contract_version}-{source_hash[:12]}"
        root.mkdir(parents=True, exist_ok=True)
        outputs: list[dict[str, object]] = []
        for season in sorted(selected):
            for horizon in FeatureHorizon:
                frame = self.features_for_horizon(features, horizon)
                frame = frame[frame["season"] == season].copy()
                if frame.empty:
                    continue
                frame = frame.sort_values(["round", "driver_identity_key"], kind="stable")
                relative = Path(f"season={season}") / f"horizon={horizon.value}" / "features.parquet"
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                checkpoint_path = path.with_suffix(".checkpoint.json")
                if checkpoint_path.exists() and path.exists():
                    checkpoint = json.loads(checkpoint_path.read_text())
                    digest = sha256(path.read_bytes()).hexdigest()
                    if (
                        checkpoint.get("source_manifest_sha256") == source_hash
                        and checkpoint.get("parquet_sha256") == digest
                        and checkpoint.get("rows") == len(frame)
                        and checkpoint.get("status") == "complete"
                    ):
                        outputs.append({"path": relative.as_posix(), **checkpoint})
                        continue
                    raise ValueError(f"checkpoint mismatch for {relative}; write a new dataset version instead")
                frame.to_parquet(path, index=False, engine="pyarrow", compression="zstd")
                digest = sha256(path.read_bytes()).hexdigest()
                checkpoint = {
                    "season": int(season),
                    "session": horizon.value,
                    "source_manifest_sha256": source_hash,
                    "parquet_sha256": digest,
                    "rows": int(len(frame)),
                    "status": "complete",
                }
                checkpoint_path.write_bytes(_canonical_json(checkpoint))
                outputs.append({"path": relative.as_posix(), **checkpoint})
        manifest = {
            "contract_version": self.contract_version,
            "source_snapshots": source_manifest,
            "source_manifest_sha256": source_hash,
            "dataset_quality": AVAILABILITY_ARCHIVED_UNKNOWN_AS_OF,
            "asof_evaluation_eligible": False,
            "feature_dictionary": self.registry.dictionary(),
            "outputs": outputs,
            "audit": report,
        }
        manifest_bytes = _canonical_json(manifest)
        manifest_hash = sha256(manifest_bytes).hexdigest()
        manifest_path = root / "manifest.json"
        if manifest_path.exists() and manifest_path.read_bytes() != manifest_bytes:
            raise ValueError("immutable manifest collision; choose a new dataset version")
        if not manifest_path.exists():
            manifest_path.write_bytes(manifest_bytes)
            (root / "manifest.sha256").write_text(f"{manifest_hash}  manifest.json\n")
        return {"root": str(root), "manifest_sha256": manifest_hash, **manifest}


def reconstruct_dataset(archive: Path, root: Path, *, seasons: Iterable[int] | None = None) -> dict[str, object]:
    """Offline command surface for rebuilding a versioned dataset from raw snapshots."""
    return DatasetBackfill.from_jolpica_archive(archive).write(root, seasons=seasons)
