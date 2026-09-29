"""Append-only forecast provenance records and atomic publication selection."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from gridoracle.provenance.artifacts import (
    ArtifactIntegrityError,
    ContentAddressedArtifactStore,
)


class ProvenanceError(ValueError):
    """A forecast cannot be stored or published with trustworthy lineage."""


class IdempotencyConflict(ProvenanceError):
    """A retry key was reused with different immutable content."""


def _utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ProvenanceError("all provenance timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime | None) -> str | None:
    value = _utc(value)
    return value.isoformat() if value is not None else None


def _canonical(value: Any) -> str:
    """Canonical representation used for retry and output integrity hashes."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _row_as_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def _database_json(value: Mapping[str, Any]) -> str:
    """Bind JSON through textual SQL consistently on PostgreSQL and SQLite."""
    return _canonical(dict(value))


def _loaded_json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


@dataclass(frozen=True)
class ForecastEntry:
    """One immutable predicted field entry keyed by stable event-entry identity."""

    entry_key: str
    output: Mapping[str, Any]


@dataclass(frozen=True)
class ForecastRunInput:
    """The complete lineage required before a field may be published."""

    race_id: int
    horizon: str
    input_cutoff_at: datetime | None
    issue_at: datetime | None
    source_available_at: datetime | None
    provenance_grade: str
    expected_entry_count: int
    idempotency_key: str
    input_manifest: Mapping[str, Any]
    raw_snapshot_id: str | None = None
    result_revision_id: int | None = None
    dataset_id: str | None = None
    feature_snapshot_id: str | None = None
    model_manifest_id: str | None = None
    calibrator_manifest_id: str | None = None
    reproduction_tolerance: float = 1e-12

    def validate(self) -> None:
        if self.horizon not in {"pre_weekend", "post_qualifying"}:
            raise ProvenanceError("horizon must be pre_weekend or post_qualifying")
        if self.provenance_grade not in {
            "verified",
            "observed",
            "legacy_unverified",
        }:
            raise ProvenanceError("unrecognised provenance grade")
        if not self.idempotency_key or len(self.idempotency_key) > 200:
            raise ProvenanceError(
                "idempotency_key is required and must be at most 200 characters"
            )
        if self.expected_entry_count < 1:
            raise ProvenanceError("expected_entry_count must be positive")
        if self.reproduction_tolerance < 0:
            raise ProvenanceError("reproduction_tolerance cannot be negative")
        cutoff = _utc(self.input_cutoff_at)
        issue = _utc(self.issue_at)
        available = _utc(self.source_available_at)
        if self.provenance_grade != "legacy_unverified" and (
            cutoff is None or issue is None or available is None
        ):
            raise ProvenanceError(
                "verified and observed runs require cutoff, issue, and source "
                "availability times"
            )
        if cutoff is not None and issue is not None and cutoff > issue:
            raise ProvenanceError("input cutoff cannot be after issue time")
        if available is not None and cutoff is not None and available > cutoff:
            raise ProvenanceError(
                "source availability cannot be after the input cutoff"
            )

    def payload(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "input_cutoff_at": _timestamp(self.input_cutoff_at),
            "issue_at": _timestamp(self.issue_at),
            "source_available_at": _timestamp(self.source_available_at),
            "input_manifest": dict(self.input_manifest),
        }


class ImmutableProvenanceStore:
    """Store append-only run lineage over the WP03 additive schema.

    The database migration makes every lineage and output table write-once. A
    publication is therefore one transaction that observes a complete staged
    field and inserts an immutable race/horizon pointer. Retrying the same
    inputs returns the original identifiers; conflicting retries fail.
    """

    def __init__(self, engine: Engine, artifacts: ContentAddressedArtifactStore):
        self.engine = engine
        self.artifacts = artifacts

    def record_raw_snapshot(
        self,
        *,
        snapshot_id: str,
        provider: str,
        retrieved_at: datetime,
        source_available_at: datetime | None,
        artifact_path: str,
        sha256: str,
        manifest: Mapping[str, Any],
        provenance_grade: str = "verified",
    ) -> str:
        self._verify_artifact(artifact_path, sha256)
        self._insert_idempotent(
            "raw_provider_snapshots",
            "snapshot_id",
            snapshot_id,
            {
                "snapshot_id": snapshot_id,
                "provider": provider,
                "retrieved_at": _timestamp(retrieved_at),
                "source_available_at": _timestamp(source_available_at),
                "artifact_path": artifact_path,
                "sha256": sha256,
                "manifest": _database_json(manifest),
                "provenance_grade": provenance_grade,
            },
        )
        return snapshot_id

    def record_dataset(
        self,
        *,
        dataset_id: str,
        artifact_path: str,
        sha256: str,
        manifest: Mapping[str, Any],
    ) -> str:
        return self._record_manifest(
            "dataset_manifests",
            "dataset_id",
            dataset_id,
            artifact_path,
            sha256,
            manifest,
        )

    def record_feature_snapshot(
        self,
        *,
        feature_snapshot_id: str,
        dataset_id: str,
        artifact_path: str,
        sha256: str,
        manifest: Mapping[str, Any],
    ) -> str:
        self._verify_artifact(artifact_path, sha256)
        self._insert_idempotent(
            "feature_snapshots",
            "feature_snapshot_id",
            feature_snapshot_id,
            {
                "feature_snapshot_id": feature_snapshot_id,
                "dataset_id": dataset_id,
                "artifact_path": artifact_path,
                "sha256": sha256,
                "manifest": _database_json(manifest),
            },
        )
        return feature_snapshot_id

    def record_model_manifest(
        self,
        *,
        model_manifest_id: str,
        model_id: str,
        artifact_path: str,
        sha256: str,
        manifest: Mapping[str, Any],
        model_version_id: int | None = None,
    ) -> str:
        self._verify_artifact(artifact_path, sha256)
        expected_path = self.artifacts.model_path(model_id, sha256)
        if artifact_path != expected_path:
            raise ProvenanceError(
                "model ID/artifact path mismatch: model artifacts must use "
                f"{expected_path}"
            )
        self._insert_idempotent(
            "model_manifests",
            "model_manifest_id",
            model_manifest_id,
            {
                "model_manifest_id": model_manifest_id,
                "model_id": model_id,
                "model_version_id": model_version_id,
                "artifact_path": artifact_path,
                "sha256": sha256,
                "manifest": _database_json(manifest),
            },
        )
        return model_manifest_id

    def record_calibrator_manifest(
        self,
        *,
        calibrator_manifest_id: str,
        model_manifest_id: str,
        artifact_path: str,
        sha256: str,
        manifest: Mapping[str, Any],
    ) -> str:
        return self._record_manifest(
            "calibrator_manifests",
            "calibrator_manifest_id",
            calibrator_manifest_id,
            artifact_path,
            sha256,
            manifest,
            extra={"model_manifest_id": model_manifest_id},
        )

    def create_forecast_run(self, run: ForecastRunInput) -> str:
        """Create, or exactly replay, a staged immutable forecast run."""
        run.validate()
        if run.provenance_grade != "legacy_unverified" and any(
            reference is None
            for reference in (
                run.raw_snapshot_id,
                run.dataset_id,
                run.feature_snapshot_id,
                run.model_manifest_id,
                run.calibrator_manifest_id,
            )
        ):
            raise ProvenanceError(
                "verified and observed runs require raw, dataset, feature, model, "
                "and calibrator manifests"
            )
        run_id = _digest(run.payload())
        values = {
            "forecast_run_id": run_id,
            "idempotency_key": run.idempotency_key,
            "race_id": run.race_id,
            "horizon": run.horizon,
            "input_cutoff_at": _timestamp(run.input_cutoff_at),
            "issue_at": _timestamp(run.issue_at),
            "source_available_at": _timestamp(run.source_available_at),
            "provenance_grade": run.provenance_grade,
            "expected_entry_count": run.expected_entry_count,
            "input_manifest": _database_json(run.input_manifest),
            "raw_snapshot_id": run.raw_snapshot_id,
            "result_revision_id": run.result_revision_id,
            "dataset_id": run.dataset_id,
            "feature_snapshot_id": run.feature_snapshot_id,
            "model_manifest_id": run.model_manifest_id,
            "calibrator_manifest_id": run.calibrator_manifest_id,
            "reproduction_tolerance": run.reproduction_tolerance,
            "run_fingerprint": _digest(run.payload()),
        }
        with self.engine.begin() as conn:
            existing = conn.execute(
                text(
                    "SELECT forecast_run_id, run_fingerprint FROM forecast_runs "
                    "WHERE idempotency_key = :idempotency_key"
                ),
                {"idempotency_key": run.idempotency_key},
            ).fetchone()
            if existing is not None:
                if existing.run_fingerprint != values["run_fingerprint"]:
                    raise IdempotencyConflict(
                        "idempotency key already identifies a different forecast run"
                    )
                return str(existing.forecast_run_id)
            try:
                conn.execute(
                    text(
                        """
                        INSERT INTO forecast_runs
                        (forecast_run_id, idempotency_key, race_id, horizon,
                         input_cutoff_at, issue_at, source_available_at,
                         provenance_grade, expected_entry_count, input_manifest,
                         raw_snapshot_id, result_revision_id, dataset_id,
                         feature_snapshot_id, model_manifest_id,
                         calibrator_manifest_id, reproduction_tolerance,
                         run_fingerprint)
                        VALUES
                        (:forecast_run_id, :idempotency_key, :race_id, :horizon,
                         :input_cutoff_at, :issue_at, :source_available_at,
                         :provenance_grade, :expected_entry_count, :input_manifest,
                         :raw_snapshot_id, :result_revision_id, :dataset_id,
                         :feature_snapshot_id, :model_manifest_id,
                         :calibrator_manifest_id, :reproduction_tolerance,
                         :run_fingerprint)
                        """
                    ),
                    values,
                )
            except IntegrityError as exc:
                message = "forecast run identity already exists"
                raise IdempotencyConflict(message) from exc
        return run_id

    def add_entry_outputs(
        self, forecast_run_id: str, entries: Iterable[ForecastEntry]
    ) -> int:
        """Append a complete retry-safe batch of output rows to a staged run."""
        materialised = list(entries)
        if not materialised:
            raise ProvenanceError("a forecast field requires at least one entry output")
        keys = [entry.entry_key for entry in materialised]
        if len(keys) != len(set(keys)) or any(not key for key in keys):
            raise ProvenanceError("entry output keys must be non-empty and unique")
        rows = [
            {
                "forecast_run_id": forecast_run_id,
                "entry_key": entry.entry_key,
                "output": _database_json(entry.output),
                "output_sha256": _digest(dict(entry.output)),
            }
            for entry in materialised
        ]
        with self.engine.begin() as conn:
            self._require_run(conn, forecast_run_id)
            for row in rows:
                existing = conn.execute(
                    text(
                        "SELECT output_sha256 FROM forecast_entry_outputs "
                        "WHERE forecast_run_id = :forecast_run_id "
                        "AND entry_key = :entry_key"
                    ),
                    row,
                ).fetchone()
                if existing is None:
                    conn.execute(
                        text(
                            """
                            INSERT INTO forecast_entry_outputs
                            (forecast_run_id, entry_key, output, output_sha256)
                            VALUES (:forecast_run_id, :entry_key, :output,
                                    :output_sha256)
                            """
                        ),
                        row,
                    )
                elif existing.output_sha256 != row["output_sha256"]:
                    raise IdempotencyConflict(
                        f"entry {row['entry_key']} already has different "
                        "immutable output"
                    )
        return len(rows)

    def publish(
        self,
        forecast_run_id: str,
        *,
        race_start_at: datetime,
        published_at: datetime,
    ) -> str:
        """Atomically make a complete pre-race run the pointer for its horizon."""
        race_start_at = _utc(race_start_at)
        published_at = _utc(published_at)
        assert race_start_at is not None and published_at is not None
        with self.engine.begin() as conn:
            run = self._require_run(conn, forecast_run_id)
            if run["provenance_grade"] == "legacy_unverified":
                raise ProvenanceError(
                    "legacy_unverified forecasts cannot become a live publication"
                )
            issue_at = run["issue_at"]
            if issue_at is None or _utc(issue_at) >= race_start_at:
                raise ProvenanceError(
                    "post-race output cannot become a live pre-race forecast"
                )
            if published_at >= race_start_at:
                raise ProvenanceError("a live forecast must publish before race start")
            if run["result_revision_id"] is not None:
                raise ProvenanceError(
                    "a result-linked run cannot become a live pre-race forecast"
                )
            count = conn.execute(
                text(
                    "SELECT count(*) FROM forecast_entry_outputs "
                    "WHERE forecast_run_id = :forecast_run_id"
                ),
                {"forecast_run_id": forecast_run_id},
            ).scalar_one()
            if count != run["expected_entry_count"]:
                raise ProvenanceError(
                    f"incomplete field: expected {run['expected_entry_count']} "
                    f"entries, found {count}"
                )
            existing = conn.execute(
                text(
                    """
                    SELECT forecast_run_id FROM forecast_publications
                    WHERE race_id = :race_id AND horizon = :horizon
                    """
                ),
                {"race_id": run["race_id"], "horizon": run["horizon"]},
            ).fetchone()
            if existing is not None:
                if existing.forecast_run_id == forecast_run_id:
                    return forecast_run_id
                raise ProvenanceError(
                    "a different immutable run is already published for this race "
                    "and horizon"
                )
            try:
                conn.execute(
                    text(
                        """
                        INSERT INTO forecast_publications
                        (race_id, horizon, forecast_run_id, published_at)
                        VALUES (:race_id, :horizon, :forecast_run_id, :published_at)
                        """
                    ),
                    {
                        "race_id": run["race_id"],
                        "horizon": run["horizon"],
                        "forecast_run_id": forecast_run_id,
                        "published_at": _timestamp(published_at),
                    },
                )
            except IntegrityError as exc:
                raise ProvenanceError(
                    "a concurrent publisher selected another run for this race "
                    "and horizon"
                ) from exc
        return forecast_run_id

    def record_evaluation(
        self,
        *,
        evaluation_id: str,
        forecast_run_id: str,
        result_revision_id: int,
        evaluator_manifest: Mapping[str, Any],
        metrics: Mapping[str, Any],
        evaluated_at: datetime,
    ) -> str:
        """Append an evaluation revision without mutating forecast outputs."""
        with self.engine.connect() as conn:
            self._require_run(conn, forecast_run_id)
        self._insert_idempotent(
            "evaluation_runs",
            "evaluation_id",
            evaluation_id,
            {
                "evaluation_id": evaluation_id,
                "forecast_run_id": forecast_run_id,
                "result_revision_id": result_revision_id,
                "evaluator_manifest": _database_json(evaluator_manifest),
                "metrics": _database_json(metrics),
                "evaluated_at": _timestamp(evaluated_at),
            },
        )
        return evaluation_id

    def import_legacy_forecast(
        self,
        *,
        race_id: int,
        model_version_id: int | None,
        created_at: datetime | None,
        entries: Iterable[ForecastEntry],
        legacy_key: str,
    ) -> str:
        """Preserve known legacy values without fabricating unknown lineage."""
        materialised = list(entries)
        run = ForecastRunInput(
            race_id=race_id,
            horizon="pre_weekend",
            input_cutoff_at=None,
            issue_at=created_at,
            source_available_at=None,
            provenance_grade="legacy_unverified",
            expected_entry_count=len(materialised),
            idempotency_key=f"legacy:{legacy_key}",
            input_manifest={
                "legacy_model_version_id": model_version_id,
                "known_created_at": _timestamp(created_at),
                "unknown_fields": [
                    "input_cutoff_at",
                    "source_available_at",
                    "artifact_manifest",
                ],
            },
        )
        run_id = self.create_forecast_run(run)
        self.add_entry_outputs(run_id, materialised)
        return run_id

    def verify_reproduction(
        self,
        forecast_run_id: str,
        reproduce: Callable[[Mapping[str, Any]], Mapping[str, Mapping[str, Any]]],
    ) -> None:
        """Run a fresh-process reproducer and compare saved outputs by tolerance."""
        with self.engine.connect() as conn:
            run = self._require_run(conn, forecast_run_id)
            outputs = conn.execute(
                text(
                    """
                    SELECT entry_key, output FROM forecast_entry_outputs
                    WHERE forecast_run_id = :forecast_run_id ORDER BY entry_key
                    """
                ),
                {"forecast_run_id": forecast_run_id},
            ).fetchall()
        candidate = reproduce(_loaded_json(run["input_manifest"]))
        expected = {row.entry_key: _loaded_json(row.output) for row in outputs}
        if set(candidate) != set(expected):
            raise ProvenanceError(
                "reproduced entry keys do not match saved forecast output"
            )
        tolerance = float(run["reproduction_tolerance"])
        for key in expected:
            if not _within_tolerance(expected[key], candidate[key], tolerance):
                raise ProvenanceError(
                    f"reproduction differs for {key} beyond tolerance {tolerance}"
                )

    def _record_manifest(
        self,
        table: str,
        id_column: str,
        identifier: str,
        artifact_path: str,
        sha256: str,
        manifest: Mapping[str, Any],
        *,
        extra: Mapping[str, Any] | None = None,
    ) -> str:
        self._verify_artifact(artifact_path, sha256)
        values = {
            id_column: identifier,
            "artifact_path": artifact_path,
            "sha256": sha256,
            "manifest": _database_json(manifest),
            **(dict(extra) if extra else {}),
        }
        self._insert_idempotent(table, id_column, identifier, values)
        return identifier

    def _verify_artifact(self, artifact_path: str, sha256: str) -> None:
        try:
            self.artifacts.verify(artifact_path, sha256)
        except ArtifactIntegrityError as exc:
            raise ProvenanceError(str(exc)) from exc

    def _insert_idempotent(
        self, table: str, id_column: str, identifier: str, values: Mapping[str, Any]
    ) -> None:
        columns = list(values)
        placeholders = ", ".join(f":{column}" for column in columns)
        with self.engine.begin() as conn:
            existing = conn.execute(
                text(f"SELECT * FROM {table} WHERE {id_column} = :identifier"),
                {"identifier": identifier},
            ).fetchone()
            if existing is not None:
                existing_data = _row_as_dict(existing)
                for column, value in values.items():
                    if existing_data[column] != value:
                        raise IdempotencyConflict(
                            f"{table}.{identifier} already exists with different "
                            "immutable content"
                        )
                return
            conn.execute(
                text(
                    f"INSERT INTO {table} ({', '.join(columns)}) "
                    f"VALUES ({placeholders})"
                ),
                dict(values),
            )

    @staticmethod
    def _require_run(conn: Any, forecast_run_id: str) -> dict[str, Any]:
        row = conn.execute(
            text(
                "SELECT * FROM forecast_runs WHERE forecast_run_id = :forecast_run_id"
            ),
            {"forecast_run_id": forecast_run_id},
        ).fetchone()
        if row is None:
            raise ProvenanceError(f"unknown forecast run: {forecast_run_id}")
        return _row_as_dict(row)


def _within_tolerance(expected: Any, actual: Any, tolerance: float) -> bool:
    if isinstance(expected, int | float) and not isinstance(expected, bool):
        return isinstance(actual, int | float) and (
            abs(float(expected) - float(actual)) <= tolerance
        )
    if isinstance(expected, dict):
        return (
            isinstance(actual, Mapping)
            and set(expected) == set(actual)
            and all(
                _within_tolerance(expected[key], actual[key], tolerance)
                for key in expected
            )
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(
                _within_tolerance(left, right, tolerance)
                for left, right in zip(expected, actual, strict=True)
            )
        )
    return expected == actual
