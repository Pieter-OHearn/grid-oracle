"""The production job handlers: live provider data to published forecasts.

WP14's replay adapter proved these steps against recorded bytes. Here every
provider read is a fresh Jolpica observation, stored as an immutable raw
snapshot before anything derives from it. Identifiers are deterministic per
race, horizon and schedule fingerprint, so a retried job replays its stored
inputs instead of fetching new ones and conflicting with its first attempt.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from gridoracle.ops.bundle import canonical, file_digest
from gridoracle.provenance import (
    ContentAddressedArtifactStore,
    ForecastEntry,
    ForecastRunInput,
    ImmutableProvenanceStore,
)
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.benchmark.metrics import SCALARS, score_race
from pipeline.issuance import domain
from pipeline.issuance.features import (
    POST_QUALIFYING,
    PRE_WEEKEND,
    feature_records,
    qualifying_positions,
    qualifying_verified,
    race_standings,
    targets,
)
from pipeline.issuance.jolpica import JolpicaClient, Observation
from pipeline.orchestration import (
    EVALUATE,
    POST_FEATURE,
    POST_PREDICT,
    POST_PUBLISH,
    PRE_FEATURE,
    PRE_PREDICT,
    PRE_PUBLISH,
    QUALIFY_INGEST,
    RESULT_INGEST,
    Job,
    JobBlocked,
    RetryableJobError,
    qualifying_publication_ready,
)

MODEL_FORMAT = "gridoracle-fixed-baseline-v1"
# A past race is caught up only once its classification can have settled.
RESULTS_AFTER = timedelta(hours=3)
ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_CONFIG = ROOT / "docs/benchmark/v2/config.json"


def load_model(artifact_root: Path, bundle: dict[str, Any]) -> dict[str, Any]:
    """Read the bundle's fixed-baseline model; the bundle is already verified."""
    model = json.loads((artifact_root / bundle["model"]["path"]).read_bytes())
    if model.get("format") != MODEL_FORMAT:
        raise JobBlocked(f"bundle model is not a {MODEL_FORMAT} artifact")
    if set(model.get("horizons", {})) != {PRE_WEEKEND, POST_QUALIFYING}:
        raise JobBlocked("bundle model must name a baseline for both horizons")
    return model


class ProductionIssuance:
    def __init__(
        self,
        engine: Engine,
        artifact_root: Path,
        bundle: dict[str, Any],
        client: JolpicaClient,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.engine, self.bundle, self.client, self.now = engine, bundle, client, now
        self.root = artifact_root
        self.artifacts = ContentAddressedArtifactStore(artifact_root)
        self.store = ImmutableProvenanceStore(engine, self.artifacts)
        self.model = load_model(artifact_root, bundle)

    def handlers(self) -> dict[str, Callable[[Job], None]]:
        return {
            PRE_FEATURE: lambda job: self.feature(job, PRE_WEEKEND),
            PRE_PREDICT: lambda job: self.predict(job, PRE_WEEKEND),
            PRE_PUBLISH: lambda job: self.publish(job, PRE_WEEKEND),
            QUALIFY_INGEST: self.ingest_qualifying,
            POST_FEATURE: lambda job: self.feature(job, POST_QUALIFYING),
            POST_PREDICT: lambda job: self.predict(job, POST_QUALIFYING),
            POST_PUBLISH: lambda job: self.publish(job, POST_QUALIFYING),
            RESULT_INGEST: self.ingest_results,
            EVALUATE: self.evaluate,
        }

    # -- identifiers -------------------------------------------------------

    @staticmethod
    def run_key(job: Job, horizon: str) -> str:
        fingerprint = job.payload["schedule_fingerprint"][:16]
        return f"production/{job.race_id}/{fingerprint}/{horizon}"

    @staticmethod
    def qualifying_key(job: Job) -> str:
        fingerprint = job.payload["schedule_fingerprint"][:16]
        return f"production/{job.race_id}/{fingerprint}/qualifying"

    # -- stored inputs -----------------------------------------------------

    def _snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT artifact_path, sha256, retrieved_at, "
                        "source_available_at FROM raw_provider_snapshots "
                        "WHERE snapshot_id=:id"
                    ),
                    {"id": snapshot_id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        self.artifacts.verify(row["artifact_path"], row["sha256"])
        document = json.loads((self.root / row["artifact_path"]).read_bytes())
        return {**dict(row), "document": document}

    def _record(self, snapshot_id: str, document: dict, *, retrieved_at: datetime):
        ref = self.artifacts.put_bytes("providers/jolpica", canonical(document))
        self.store.record_raw_snapshot(
            snapshot_id=snapshot_id,
            provider="jolpica",
            retrieved_at=retrieved_at,
            # Jolpica publishes no availability time: the retrieval time is
            # the only observed bound, so runs are graded "observed".
            source_available_at=retrieved_at,
            artifact_path=ref.path,
            sha256=ref.sha256,
            manifest={"kind": document.get("kind"), "url": document.get("url")},
            provenance_grade="observed",
        )

    # -- handlers ----------------------------------------------------------

    def feature(self, job: Job, horizon: str) -> None:
        key = self.run_key(job, horizon)
        stored = self._snapshot(f"{key}/raw")
        if stored is None:
            stored_document = self._observe(job, horizon)
        else:
            stored_document = stored["document"]
        observation = stored_document["observation"]
        records = feature_records(
            season=job.payload["season"],
            round_number=job.payload["round"],
            horizon=horizon,
            cutoff=observation["observed_at"],
            entries=observation["field"],
            standings=observation["standings"],
            qualifying=observation.get("qualifying"),
        )
        ref = self.artifacts.put_bytes("features/production", canonical(records))
        self.store.record_feature_snapshot(
            feature_snapshot_id=f"{key}/features",
            dataset_id=self.bundle["dataset_id"],
            artifact_path=ref.path,
            sha256=ref.sha256,
            manifest={
                "horizon": horizon,
                "cutoff": observation["observed_at"],
                "feature_schema": self.bundle["feature_schema"]["sha256"],
            },
        )

    def _observe(self, job: Job, horizon: str) -> dict[str, Any]:
        """Fetch, freeze and store this horizon's inputs once."""
        season, round_number = job.payload["season"], job.payload["round"]
        with self.engine.begin() as conn:
            if horizon == PRE_WEEKEND:
                domain.carry_forward_field(conn, job.race_id)
            entries = domain.field(conn, job.race_id)
        if not entries:
            raise JobBlocked("the event has no active field")
        results = self.client.results(season)
        observed_at = self.now()
        if horizon == PRE_WEEKEND:
            cutoff = datetime.fromisoformat(job.payload["pre_cutoff"])
            if observed_at >= cutoff:
                raise JobBlocked("pre-weekend inputs were observed after the cutoff")
        drivers = {entry.key: domain.provider_id(entry.driver_key) for entry in entries}
        if None in drivers.values():
            raise JobBlocked("the field has a driver without a Jolpica identity")
        standings = race_standings(results.races(), season, round_number, drivers.values())
        qualifying = None
        provenance = "previous_round_classification"
        if horizon == POST_QUALIFYING:
            snapshot = self._snapshot(self.qualifying_key(job))
            if snapshot is None:
                raise JobBlocked("post-qualifying needs the stored qualifying")
            races = snapshot["document"]["payload"]["MRData"]["RaceTable"]["Races"]
            qualifying = qualifying_positions(races[0])
            provenance = "qualifying_classification"
        document = {
            **results.document(),
            "observation": {
                "observed_at": observed_at.isoformat(),
                "horizon": horizon,
                "race": {"race_id": job.race_id, "season": season, "round": round_number},
                "field": [
                    {
                        "key": entry.key,
                        "driver": drivers[entry.key],
                        "team_key": entry.team_key,
                        "provenance": provenance,
                    }
                    for entry in entries
                ],
                "standings": standings,
                "qualifying": qualifying,
                "qualifying_snapshot": (self.qualifying_key(job) if horizon == POST_QUALIFYING else None),
            },
        }
        self._record(
            f"{self.run_key(job, horizon)}/raw",
            document,
            retrieved_at=results.retrieved_at,
        )
        return document

    def predict(self, job: Job, horizon: str) -> None:
        # Imported here: the model stack is the worker's, not the scheduler's.
        from pipeline.selection.interface import Baseline
        from pipeline.selection.outputs import Field

        key = self.run_key(job, horizon)
        raw = self._snapshot(f"{key}/raw")
        with self.engine.connect() as conn:
            feature = (
                conn.execute(
                    text("SELECT artifact_path, sha256 FROM feature_snapshots WHERE feature_snapshot_id=:id"),
                    {"id": f"{key}/features"},
                )
                .mappings()
                .one_or_none()
            )
        if raw is None or feature is None:
            raise JobBlocked("prediction needs the stored feature snapshot")
        self.artifacts.verify(feature["artifact_path"], feature["sha256"])
        records = json.loads((self.root / feature["artifact_path"]).read_bytes())
        frame = pd.DataFrame(records)
        cutoff = datetime.fromisoformat(records[0]["cutoff"])
        season, round_number = job.payload["season"], job.payload["round"]
        field = Field(
            f"{season}/{round_number}",
            horizon,
            cutoff.isoformat(),
            key,
            tuple(frame.driver_identity_key),
            teams=tuple(zip(frame.driver_identity_key, frame.constructor_identity_key, strict=True)),
        )
        prediction = Baseline(
            self.model["horizons"][horizon],
            horizon,
            {"model_sha256": self.bundle["model"]["sha256"]},
        ).predict(frame, field)
        run = ForecastRunInput(
            race_id=job.race_id,
            horizon=horizon,
            input_cutoff_at=cutoff,
            issue_at=cutoff,
            source_available_at=raw["source_available_at"],
            provenance_grade="observed",
            expected_entry_count=len(records),
            idempotency_key=key,
            input_manifest={
                "contract": domain.CONTRACT_VERSION,
                "baseline": self.model["horizons"][horizon],
                "temperature": self.model["temperature"],
                "field_sha256": field.sha256,
                "schedule_fingerprint": job.payload["schedule_fingerprint"],
                "bundle_model_sha256": self.bundle["model"]["sha256"],
                "entry_provenance": records[0]["entry_provenance"],
            },
            raw_snapshot_id=f"{key}/raw",
            dataset_id=self.bundle["dataset_id"],
            feature_snapshot_id=f"{key}/features",
            model_manifest_id=self.bundle["model_manifest_id"],
            calibrator_manifest_id=self.bundle["calibrator_manifest_id"],
        )
        run_id = self.store.create_forecast_run(run)
        with self.engine.connect() as conn:
            published = conn.execute(
                text("SELECT 1 FROM forecast_publications WHERE forecast_run_id=:run"),
                {"run": run_id},
            ).first()
        if published:
            # A replay after publication: the complete field is already stored.
            return
        self.store.add_entry_outputs(
            run_id,
            [
                ForecastEntry(
                    entry,
                    {
                        "win_probability": prediction["winner"][entry],
                        "rank": prediction["order"].index(entry) + 1,
                    },
                )
                for entry in field.entries
            ],
        )

    def publish(self, job: Job, horizon: str) -> None:
        with self.engine.connect() as conn:
            run_id = conn.execute(
                text("SELECT forecast_run_id FROM forecast_runs WHERE idempotency_key=:key"),
                {"key": self.run_key(job, horizon)},
            ).scalar_one_or_none()
        if run_id is None:
            raise JobBlocked("publication needs the staged forecast run")
        self.store.publish(run_id, published_at=self.now())

    def ingest_qualifying(self, job: Job) -> None:
        key = self.qualifying_key(job)
        stored = self._snapshot(key)
        if stored is None:
            observation = self.client.qualifying(job.payload["season"], job.payload["round"])
            races = observation.races()
            if not races or not races[0].get("QualifyingResults"):
                raise RetryableJobError("qualifying is not published yet")
            if not qualifying_verified(races[0]):
                raise RetryableJobError("qualifying classification is incomplete")
            self._record(key, observation.document(), retrieved_at=observation.retrieved_at)
            race = races[0]
        else:
            race = stored["document"]["payload"]["MRData"]["RaceTable"]["Races"][0]
        with self.engine.begin() as conn:
            entrants = domain.record_qualifying(conn, job.race_id, race)
            size = domain.revise_field(conn, job.race_id, [(d, t) for d, t, _ in entrants])
        qualifying_publication_ready(
            ingested_entries=len(entrants),
            expected_entries=size,
            grid_verified=qualifying_verified(race),
        )

    def ingest_results(self, job: Job) -> None:
        if not self._ingest_round(job.race_id, job.payload["season"], job.payload["round"]):
            raise RetryableJobError("the race classification is not published yet")

    def _ingest_round(self, race_id: int, season: int, round_number: int) -> bool:
        """Store a published classification and its revision; False if absent."""
        observation = self.client.results(season, round_number)
        races = observation.races()
        if not races or not races[0].get("Results"):
            return False
        race = races[0]
        digest = domain.classification_digest(race["Results"])
        self._record(
            f"production/{race_id}/results/{digest[:16]}",
            observation.document(),
            retrieved_at=observation.retrieved_at,
        )
        with self.engine.begin() as conn:
            domain.record_results(conn, race_id, race, recorded_at=self.now())
        return True

    def evaluate(self, job: Job) -> None:
        with self.engine.connect() as conn:
            revision = conn.execute(
                text("SELECT id, reason FROM result_revisions WHERE race_id=:race ORDER BY revision DESC LIMIT 1"),
                {"race": job.race_id},
            ).one_or_none()
            runs = (
                conn.execute(
                    text("SELECT forecast_run_id FROM forecast_publications WHERE race_id=:race ORDER BY horizon"),
                    {"race": job.race_id},
                )
                .scalars()
                .all()
            )
        if revision is None:
            raise JobBlocked("evaluation needs a recorded result revision")
        if not runs:
            return
        digest = revision.reason.rsplit("sha256:", 1)[-1]
        snapshot = self._snapshot(f"production/{job.race_id}/results/{digest}")
        if snapshot is None:
            raise JobBlocked("the result revision has no stored provider snapshot")
        race = snapshot["document"]["payload"]["MRData"]["RaceTable"]["Races"][0]
        config = json.loads(BENCHMARK_CONFIG.read_text())
        for run_id in runs:
            evaluation_id = f"{run_id}/{revision.id}"
            with self.engine.connect() as conn:
                if conn.execute(
                    text("SELECT 1 FROM evaluation_runs WHERE evaluation_id=:id"),
                    {"id": evaluation_id},
                ).first():
                    continue
                outputs = conn.execute(
                    text(
                        "SELECT o.entry_key, o.output, d.identity_key "
                        "FROM forecast_entry_outputs o JOIN event_entries e "
                        "ON 'entry:' || e.id = o.entry_key "
                        "JOIN drivers d ON d.id = e.driver_id "
                        "WHERE o.forecast_run_id=:run"
                    ),
                    {"run": run_id},
                ).fetchall()
            field = {row.entry_key: domain.provider_id(row.identity_key) for row in outputs}
            saved = {
                row.entry_key: (json.loads(row.output) if isinstance(row.output, str) else row.output)
                for row in outputs
            }
            prediction = {
                "order": sorted(saved, key=lambda entry: saved[entry]["rank"]),
                "winner": {entry: saved[entry]["win_probability"] for entry in saved},
            }
            cohort, outside = targets(field, race)
            scored = score_race(cohort, prediction, sorted(field), config)
            values = {name: scored[name] for name in SCALARS}
            self.store.record_evaluation(
                evaluation_id=evaluation_id,
                forecast_run_id=run_id,
                result_revision_id=revision.id,
                evaluator_manifest={
                    "public_contract": "wp12-v1",
                    "config_sha256": file_digest(BENCHMARK_CONFIG),
                    "classified_outside_field": outside,
                },
                metrics={
                    "values": values,
                    "observations": {k: int(v is not None) for k, v in values.items()},
                },
                evaluated_at=self.now(),
            )

    def reconcile(self, season: int) -> list:
        """Sync the season and return the schedules the ledger should hold.

        A past race without a stored classification is caught up here, which
        covers a new installation and a result job that ran out of retries.
        Only events whose race is still ahead get a job graph, and only once
        their field can be opened: an event far ahead waits until the round
        before it has a classification, so its graph never changes when the
        field appears.
        """
        now = self.now()
        observation: Observation = self.client.schedule(season)
        events = domain.parse_schedule(observation.races())
        with self.engine.begin() as conn:
            rounds = domain.sync_calendar(conn, events)
            completed = {
                row.id
                for row in conn.execute(
                    text("SELECT id FROM races WHERE season=:season AND is_completed"),
                    {"season": season},
                )
            }
        for event in events:
            race_id = rounds[event.round_number]
            if event.race_start + RESULTS_AFTER <= now and race_id not in completed:
                self._ingest_round(race_id, event.season, event.round_number)
        schedules = []
        with self.engine.begin() as conn:
            for event in events:
                if event.race_start <= now:
                    continue
                race_id = rounds[event.round_number]
                try:
                    domain.carry_forward_field(conn, race_id)
                except JobBlocked:
                    continue
                schedules.append(domain.schedule(conn, race_id))
        return schedules
