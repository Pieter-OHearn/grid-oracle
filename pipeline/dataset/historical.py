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
DATASET_CONTRACT_VERSION = "2026.2-wp05"


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
        disallowed = self.forbidden_for(horizon)
        present = disallowed & set(frame.columns)
        if present:
            raise ValueError(f"features forbidden at {horizon}: {sorted(present)}")

    def forbidden_for(self, horizon: FeatureHorizon) -> set[str]:
        """Return feature names that must not exist in this horizon's frame."""
        return {definition.name for definition in self._definitions.values() if horizon not in definition.horizons}

    def fingerprint(self) -> str:
        """Stable registry digest included in every output/checkpoint contract."""
        return sha256(_canonical_json(self.dictionary())).hexdigest()

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
        conflicted: dict[str, set[tuple[int, int, str]]] = {
            "results": set(),
            "qualifying": set(),
        }
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
                    if key in conflicted[kind]:
                        continue
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
                        # Jolpica's numeric ``position`` is a provider order and
                        # also appears on R/D/W/N rows.  Only positionText proves
                        # an official classified result for the WP02 target.
                        official_rank = _positive_int(row.get("positionText"))
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
                        conflicted[kind].add(key)
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
        """Race-only competition ranks; equal points share one rank."""
        values: dict[tuple[int, int, str], int] = {}
        for season, season_rows in frame.groupby("season", sort=True):
            totals: defaultdict[str, float] = defaultdict(float)
            for round_number, event_rows in season_rows.groupby("round", sort=True):
                ranks: dict[str, int] = {}
                previous_points: float | None = None
                rank = 0
                for position, entity in enumerate(sorted(totals, key=lambda item: (-totals[item], item)), start=1):
                    points = totals[entity]
                    if points != previous_points:
                        rank = position
                        previous_points = points
                    ranks[entity] = rank
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

    @staticmethod
    def _rolling_last_three(values: pd.Series) -> pd.Series:
        return values.shift().rolling(3, min_periods=1).mean()

    def _add_driver_feature_tiers(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Add vectorized driver recency and reliability features."""
        classified = rows["finish_position"].where(rows["target_eligible"])
        rows["driver_finish_mean_last_3"] = classified.groupby(rows["driver_identity_key"], sort=False).transform(
            self._rolling_last_three
        )
        rows["driver_recency_races"] = rows.groupby("driver_identity_key", sort=False).cumcount()
        reliable = (
            rows["canonical_status"]
            .isin({CanonicalResultStatus.FINISHED.value, CanonicalResultStatus.LAPPED.value})
            .astype(float)
        )
        rows["driver_reliability_rate_last_3"] = reliable.groupby(rows["driver_identity_key"], sort=False).transform(
            self._rolling_last_three
        )
        return rows

    def _add_constructor_feature_tiers(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Aggregate once per constructor/race before vectorized form windows."""
        classified = rows["finish_position"].where(rows["target_eligible"])
        constructor_race = (
            rows.assign(classified_finish=classified)
            .groupby(["season", "round", "constructor_identity_key"], as_index=False, sort=True)
            .agg(constructor_finish=("classified_finish", "mean"))
        )
        constructor_race["constructor_finish_mean_last_3"] = constructor_race.groupby(
            "constructor_identity_key", sort=False
        )["constructor_finish"].transform(self._rolling_last_three)
        constructor_race["constructor_recency_races"] = constructor_race.groupby(
            "constructor_identity_key", sort=False
        ).cumcount()
        return rows.merge(
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

    def _add_standing_features(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Attach explicitly race-only, tie-safe standings features."""
        rows["driver_championship_position_race_only"] = self._standings(rows, "driver_identity_key")
        rows["constructor_championship_position_race_only"] = self._standings(rows, "constructor_identity_key")
        return rows

    @staticmethod
    def _join_qualifying(rows: pd.DataFrame, qualifying: pd.DataFrame) -> pd.DataFrame:
        """Join post-qualifying pace fields without supplying a grid proxy."""
        qualifying_rows = qualifying.reindex(
            columns=["season", "round", "driver_identity_key", "qualifying_position"]
        ).copy()
        field_sizes = qualifying_rows.groupby(["season", "round"])["driver_identity_key"].transform("nunique")
        qualifying_rows["qualifying_normalized_position"] = qualifying_rows["qualifying_position"] / field_sizes
        return rows.merge(
            qualifying_rows,
            on=["season", "round", "driver_identity_key"],
            how="left",
            validate="one_to_one",
        )

    @staticmethod
    def _common_columns() -> list[str]:
        return [
            "season",
            "round",
            "race_key",
            "driver_identity_key",
            "constructor_identity_key",
            "availability_quality",
        ]

    def _horizon_frame(self, joined: pd.DataFrame, horizon: FeatureHorizon) -> pd.DataFrame:
        """Build one horizon's structurally valid output frame."""
        common = self._common_columns()
        pre_columns = [
            *common,
            "driver_finish_mean_last_3",
            "constructor_finish_mean_last_3",
            "driver_recency_races",
            "constructor_recency_races",
            "driver_reliability_rate_last_3",
            "driver_championship_position_race_only",
            "constructor_championship_position_race_only",
        ]
        pre = joined[
            [
                *pre_columns,
            ]
        ].copy()
        pre["horizon"] = horizon.value
        pre["cutoff"] = (
            "before_first_competitive_session"
            if horizon is FeatureHorizon.PRE_WEEKEND
            else "after_verified_qualifying_before_race"
        )
        pre["asof_eligible"] = False
        pre["entry_provenance"] = "reconstructed_from_result_entry"
        if horizon is FeatureHorizon.PRE_WEEKEND:
            pre["missing__qualifying"] = True
            pre["missing__history"] = pre["driver_finish_mean_last_3"].isna()
            self.registry.validate_columns(pre, horizon)
            return pre
        pre["qualifying_position"] = joined["qualifying_position"]
        pre["qualifying_normalized_position"] = joined["qualifying_normalized_position"]
        pre["missing__qualifying"] = pre["qualifying_position"].isna()
        pre["missing__history"] = pre["driver_finish_mean_last_3"].isna()
        self.registry.validate_columns(pre, horizon)
        return pre

    def _features(self, results: pd.DataFrame, qualifying: pd.DataFrame) -> pd.DataFrame:
        """Compose feature tiers and the two independent horizon frames."""
        if results.empty:
            return pd.DataFrame()
        rows = results.copy().sort_values(["season", "round", "driver_identity_key"], kind="stable")
        rows = self._add_driver_feature_tiers(rows)
        rows = self._add_constructor_feature_tiers(rows)
        rows = self._add_standing_features(rows)
        joined = self._join_qualifying(rows, qualifying)
        return (
            pd.concat(
                [self._horizon_frame(joined, horizon) for horizon in FeatureHorizon],
                ignore_index=True,
            )
            .sort_values(["season", "round", "horizon", "driver_identity_key"], kind="stable")
            .reset_index(drop=True)
        )

    def features_for_horizon(self, features: pd.DataFrame, horizon: FeatureHorizon) -> pd.DataFrame:
        """Return a structural horizon view, removing forbidden columns entirely."""
        forbidden = self.registry.forbidden_for(horizon)
        frame = features[features["horizon"] == horizon.value].drop(columns=forbidden, errors="ignore")
        self.registry.validate_columns(frame, horizon)
        return frame

    @staticmethod
    def _audit_report(
        results: pd.DataFrame, qualifying: pd.DataFrame, features: pd.DataFrame, audit: dict[str, object]
    ) -> dict[str, object]:
        """Attach count/null coverage to reconciliation evidence."""
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
        return audit

    @staticmethod
    def _limit_to_requested_seasons(
        results: pd.DataFrame, qualifying: pd.DataFrame, seasons: set[int] | None
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Keep only history needed through the latest requested season."""
        if not seasons:
            return results, qualifying
        through_season = max(seasons)
        return (
            results[results["season"] <= through_season].copy(),
            qualifying[qualifying["season"] <= through_season].copy(),
        )

    def _build_reconciled(
        self,
        results: pd.DataFrame,
        qualifying: pd.DataFrame,
        audit: dict[str, object],
        seasons: set[int] | None,
    ) -> tuple[pd.DataFrame, dict[str, object]]:
        scoped_results, scoped_qualifying = self._limit_to_requested_seasons(results, qualifying, seasons)
        features = self._features(scoped_results, scoped_qualifying)
        if seasons:
            features = features[features["season"].isin(seasons)].reset_index(drop=True)
            scoped_results = scoped_results[scoped_results["season"].isin(seasons)]
            scoped_qualifying = scoped_qualifying[scoped_qualifying["season"].isin(seasons)]
        return features, self._audit_report(scoped_results, scoped_qualifying, features, dict(audit))

    def build(self, *, seasons: Iterable[int] | None = None) -> tuple[pd.DataFrame, dict[str, object]]:
        """Build all or selected output seasons while retaining required history."""
        results, qualifying, audit = self._reconcile()
        requested = set(seasons) if seasons is not None else None
        return self._build_reconciled(results, qualifying, audit, requested)

    def _feature_contract_hash(self) -> str:
        """Fingerprint implementation and registry so stale frames get a new root."""
        return sha256(
            _canonical_json(
                {
                    "contract_version": self.contract_version,
                    "implementation_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                    "registry_sha256": self.registry.fingerprint(),
                }
            )
        ).hexdigest()

    @staticmethod
    def _frame_hash(frame: pd.DataFrame) -> str:
        normalized = frame.where(pd.notna(frame), None)
        return sha256(_canonical_json(normalized.to_dict(orient="records"))).hexdigest()

    @staticmethod
    def _checkpoint_path(root: Path, season: int, horizon: FeatureHorizon) -> tuple[Path, Path, Path]:
        relative = Path(f"season={season}") / f"horizon={horizon.value}" / "features.parquet"
        path = root / relative
        return relative, path, path.with_suffix(".checkpoint.json")

    @staticmethod
    def _checkpoint_key(record: Mapping[str, object]) -> tuple[int, str]:
        return int(record["season"]), str(record["session"])

    def _read_checkpoints(self, root: Path, source_hash: str, feature_hash: str) -> list[dict[str, object]]:
        """Read every verified checkpoint so partial runs compose one manifest."""
        outputs: list[dict[str, object]] = []
        for checkpoint_path in sorted(root.glob("season=*/horizon=*/features.checkpoint.json")):
            checkpoint = json.loads(checkpoint_path.read_text())
            relative = checkpoint_path.with_suffix("").with_suffix(".parquet").relative_to(root)
            parquet_path = root / relative
            if (
                checkpoint.get("source_manifest_sha256") != source_hash
                or checkpoint.get("feature_contract_sha256") != feature_hash
                or not parquet_path.is_file()
                or checkpoint.get("parquet_sha256") != sha256(parquet_path.read_bytes()).hexdigest()
            ):
                raise ValueError(f"checkpoint mismatch for {relative}; create a new dataset version")
            outputs.append({"path": relative.as_posix(), **checkpoint})
        return sorted(outputs, key=lambda record: (int(record["season"]), str(record["session"])))

    def write(self, root: Path, *, seasons: Iterable[int] | None = None) -> dict[str, object]:
        """Write versioned Parquet, checkpoints and an immutable manifest.

        ``seasons`` permits resumable backfills.  Completed season/session
        checkpoint data is content-addressed by the source snapshot manifest.
        """
        results, qualifying, audit = self._reconcile()
        available = set(int(season) for season in results["season"].unique())
        selected = set(seasons) if seasons is not None else available
        unknown = selected - available
        if unknown:
            raise ValueError(f"requested seasons absent from source snapshots: {sorted(unknown)}")
        features, report = self._build_reconciled(results, qualifying, audit, selected)
        source_manifest = self.source_manifest()
        source_hash = sha256(_canonical_json(source_manifest)).hexdigest()
        feature_hash = self._feature_contract_hash()
        root = root / f"dataset-{self.contract_version}-{source_hash[:12]}-{feature_hash[:12]}"
        root.mkdir(parents=True, exist_ok=True)
        horizon_frames = {horizon: self.features_for_horizon(features, horizon) for horizon in FeatureHorizon}
        for season in sorted(selected):
            for horizon in FeatureHorizon:
                frame = horizon_frames[horizon]
                frame = frame[frame["season"] == season].copy()
                if frame.empty:
                    continue
                frame = frame.sort_values(["round", "driver_identity_key"], kind="stable")
                frame_hash = self._frame_hash(frame)
                relative, path, checkpoint_path = self._checkpoint_path(root, season, horizon)
                path.parent.mkdir(parents=True, exist_ok=True)
                if checkpoint_path.exists() and path.exists():
                    checkpoint = json.loads(checkpoint_path.read_text())
                    digest = sha256(path.read_bytes()).hexdigest()
                    if (
                        checkpoint.get("source_manifest_sha256") == source_hash
                        and checkpoint.get("feature_contract_sha256") == feature_hash
                        and checkpoint.get("feature_frame_sha256") == frame_hash
                        and checkpoint.get("parquet_sha256") == digest
                        and checkpoint.get("rows") == len(frame)
                        and checkpoint.get("status") == "complete"
                    ):
                        continue
                    raise ValueError(f"checkpoint mismatch for {relative}; write a new dataset version instead")
                frame.to_parquet(path, index=False, engine="pyarrow", compression="zstd")
                digest = sha256(path.read_bytes()).hexdigest()
                checkpoint = {
                    "season": int(season),
                    "session": horizon.value,
                    "source_manifest_sha256": source_hash,
                    "feature_contract_sha256": feature_hash,
                    "feature_frame_sha256": frame_hash,
                    "parquet_sha256": digest,
                    "rows": int(len(frame)),
                    "status": "complete",
                }
                checkpoint_path.write_bytes(_canonical_json(checkpoint))
        outputs = self._read_checkpoints(root, source_hash, feature_hash)
        expected = {(season, horizon.value) for season in available for horizon in FeatureHorizon}
        observed = {self._checkpoint_key(output) for output in outputs}
        if expected != observed:
            return {
                "root": str(root),
                "manifest_sha256": None,
                "complete": False,
                "outputs": outputs,
            }
        if selected != available:
            _, report = self._build_reconciled(results, qualifying, audit, None)
        manifest = {
            "contract_version": self.contract_version,
            "source_snapshots": source_manifest,
            "source_manifest_sha256": source_hash,
            "feature_contract_sha256": feature_hash,
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
        return {"root": str(root), "manifest_sha256": manifest_hash, "complete": True, **manifest}


def reconstruct_dataset(archive: Path, root: Path, *, seasons: Iterable[int] | None = None) -> dict[str, object]:
    """Offline command surface for rebuilding a versioned dataset from raw snapshots."""
    return DatasetBackfill.from_jolpica_archive(archive).write(root, seasons=seasons)
