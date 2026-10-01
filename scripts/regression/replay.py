"""Synthetic weekend through real PG/ledger/baseline/provenance/API contracts.

This is a test-only adapter, not the blocked production job adapter. All issue
and availability timestamps below are synthetic simulation times, never claims
about the retained historical provider responses.
"""

import json
import os
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from gridoracle.domain.results import classify_result
from gridoracle.ops.bundle import (
    canonical,
    file_digest,
    verify_bundle,
    verify_selection,
)
from gridoracle.ops.recovery import inventory, schema_revision
from gridoracle.provenance import (
    ContentAddressedArtifactStore,
    ForecastEntry,
    ForecastRunInput,
    ImmutableProvenanceStore,
)
from pipeline.benchmark.artifacts import verify_lock
from pipeline.benchmark.metrics import SCALARS, score_race
from pipeline.ingest.fetch_qualifying import upsert_qualifying_result
from pipeline.ingest.fetch_results import upsert_race_result
from pipeline.ingest.provider import ProviderAdapter, require_keys
from pipeline.orchestration import (
    EventSchedule,
    JobLedger,
    RetryableJobError,
    qualifying_publication_ready,
    select_weather_for_interval,
)
from pipeline.selection.interface import Baseline
from pipeline.selection.outputs import Field
from scripts.db_migrate import upgrade_database

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs/regression/wp14/fixtures"


def time(value):
    return datetime.fromisoformat(value)


def checked_fixtures():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    assert file_digest(FIXTURES / "weekend.json") == manifest["weekend_sha256"]
    assert file_digest(ROOT / manifest["archive"]) == manifest["archive_sha256"]
    assert (
        file_digest(ROOT / "docs/benchmark/v2/lock.json")
        == manifest["benchmark_lock_sha256"]
    )
    verify_lock()
    return json.loads((FIXTURES / "weekend.json").read_text()), manifest


class RecordedSession:
    """Transport with no sockets; only explicitly supplied recorded bytes."""

    def __init__(self, payload, failures=0):
        self.payload, self.failures, self.calls = payload, failures, 0

    def get(self, _url, **_kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise requests.Timeout("recorded source outage")
        response = requests.Response()
        response.status_code = 200
        response._content = canonical(self.payload)
        return response


def recordings(root):
    _, manifest = checked_fixtures()
    found = {}
    with tarfile.open(ROOT / manifest["archive"]) as archive:
        for name, checksum in manifest["recordings"].items():
            raw = archive.extractfile("./" + name).read()
            from hashlib import sha256

            assert sha256(raw).hexdigest() == checksum
            payload = json.loads(raw)
            adapter = ProviderAdapter("jolpica", "GridOracle WP14 offline replay", root)
            body, path = adapter.fetch_json(
                "https://recorded.invalid/" + name,
                validator=require_keys("MRData"),
                session=RecordedSession(payload),
            )
            assert json.loads(path.read_bytes()) == payload
            races = body["MRData"]["RaceTable"]["Races"]
            assert races and body["MRData"]["limit"] == "100"
            field = "QualifyingResults" if "qualifying" in name else "Results"
            assert all(r[field] for r in races)
            found[name] = races
    return found


def initialize_legacy(engine):
    """Full historical PostgreSQL SQL, with populated sentinel before upgrade."""
    assert engine.url.database.startswith("wp14_"), "requires disposable wp14_ database"
    assert not inspect(engine).get_table_names(), "refusing nonempty target"
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cursor:
            for path in sorted((ROOT / "db/migrations").glob("*.sql")):
                cursor.execute(path.read_text())
        raw.commit()
    finally:
        raw.close()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO circuits (id,name,country,city,circuit_type"
                ",total_laps,length_km) VALUES (1,'Replay circuit','Fixt"
                "ure','Fixture','permanent',50,5)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO constructors (id,name,nationality,color_hex"
                ") VALUES (1,'Replay Team One','Fixture','#444444'),(2,'"
                "Replay Team Two','Fixture','#666666')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO model_versions (id,name,trained_at,training"
                "_races_count) VALUES (1,'WP14 baseline fixture','2026-0"
                "1-01',0)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO drivers (id,code,full_name,nationality) VAL"
                "UES (99,'OLD','Legacy sentinel','Fixture')"
            )
        )
    upgrade_database(str(engine.url))
    assert schema_revision(engine) == "20260929_05"
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT identity_key FROM drivers WHERE id=99")
            ).scalar_one()
            == "legacy:driver:99"
        )
    upgrade_database(str(engine.url))


class WeekendReplay:
    def __init__(self, engine, root: Path, *, season=2026, race_id=2026):
        fixture, self.manifest = checked_fixtures()
        fixture["season"] = season
        fixture["race_id"] = race_id
        fixture["sessions"] = {
            key: time(value).replace(year=season).isoformat()
            for key, value in fixture["sessions"].items()
        }
        fixture["qualifying_available_at"] = (
            time(fixture["qualifying_available_at"]).replace(year=season).isoformat()
        )
        self.fixture = fixture
        self.season, self.race_id = season, race_id
        self.root = root
        self.engine = engine
        self.artifacts = ContentAddressedArtifactStore(root / "artifacts")
        self.store = ImmutableProvenanceStore(engine, self.artifacts)
        self.now = time(f"{season}-04-30T13:59:00+00:00")
        self.event = EventSchedule(
            race_id, season, 1, {k: time(v) for k, v in fixture["sessions"].items()}, 22
        )
        self.ledger = JobLedger(engine, now=lambda: self.now)
        self.frames, self.runs, self.predictions, self.inputs, self.outputs = (
            {},
            {},
            {},
            {},
            {},
        )
        self.qualifying_calls = 0
        self.result_revision = None
        self._seed_domain()
        self._bundle()
        self.ledger.reconcile(self.event)

    def _seed_domain(self):
        with self.engine.begin() as conn:
            aliases = [
                ("team", "legacy:team:1", "Replay Team One"),
                ("team", "legacy:team:2", "Replay Team Two"),
                ("circuit", "legacy:circuit:1", "Replay circuit"),
            ]
            aliases.extend(
                ("driver", f"driver:internal:{i}", entry["name"])
                for i, entry in enumerate(self.fixture["entries"], 1)
            )
            for kind, key, name in aliases:
                conn.execute(
                    text(
                        "INSERT INTO entity_aliases (entity_kind,identity_key,"
                        "provider,provider_key,valid_from,valid_to,is_display_alias) "
                        "VALUES (:kind,:key,'wp14',:name,:start,:end,true) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {
                        "kind": kind,
                        "key": key,
                        "name": f"{name} · {self.season}",
                        "start": f"{self.season}-01-01",
                        "end": f"{self.season + 1}-01-01",
                    },
                )
            conn.execute(
                text(
                    "INSERT INTO races (id,season,round,name,circuit_id,date"
                    ") VALUES (:id,:season,1,'WP14 synthetic sprint weekend'"
                    ",1,:date)"
                ),
                {
                    "id": self.race_id,
                    "season": self.season,
                    "date": f"{self.season}-05-03",
                },
            )
            conn.execute(
                text(
                    "INSERT INTO season_rulesets (season,ruleset_version,sou"
                    "rce,is_current,payload) VALUES (:season,'2026.1','WP14 "
                    "synthetic',true,'{}') ON CONFLICT DO NOTHING"
                ),
                {"season": self.season},
            )
            for kind, at in self.fixture["sessions"].items():
                conn.execute(
                    text(
                        "INSERT INTO event_sessions (race_id,kind,scheduled_at,s"
                        "tatus,revision) VALUES (:id,:kind,:at,'scheduled',1)"
                    ),
                    {
                        "id": self.race_id,
                        "kind": kind.lower().replace(" ", "_"),
                        "at": at,
                    },
                )
            for i, entry in enumerate(self.fixture["entries"], 1):
                conn.execute(
                    text(
                        "INSERT INTO drivers (id,code,full_name,nationality) VAL"
                        "UES (:id,:code,:name,'Fixture') ON CONFLICT DO NOTHING"
                    ),
                    {"id": i, "code": f"T{i:02}", "name": entry["name"]},
                )
                conn.execute(
                    text(
                        "INSERT INTO event_entries (id,race_id,driver_id,constru"
                        "ctor_id,role,status,revision) VALUES (:id,:race,:driver"
                        ",:team,:role,:status,1)"
                    ),
                    {
                        "id": self.race_id * 100 + i,
                        "race": self.race_id,
                        "driver": i,
                        "team": entry["team"],
                        "role": entry["role"],
                        "status": entry["status"],
                    },
                )

    def _artifact(self, namespace, value):
        ref = self.artifacts.put_bytes(namespace, canonical(value))
        return {
            "artifact_path": ref.path,
            "sha256": ref.sha256,
            "manifest": {"synthetic": True},
        }

    def _bundle(self):
        refs = {}
        model = {
            "format": "wp14-fixed-baseline-v1",
            "horizons": {"pre_weekend": "standings", "post_qualifying": "qualifying"},
            "temperature": 4.0,
            "protocol": "wp06-v2",
        }
        for name, namespace, value in (
            ("model", "models/wp14-baseline", model),
            (
                "training_data",
                "datasets/wp14",
                {"fit": "none; fixed WP09-retained baselines"},
            ),
            (
                "feature_schema",
                "schemas/wp14",
                {
                    "features": [
                        "driver_championship_position_race_only",
                        "qualifying_position",
                        "missing__qualifying",
                    ]
                },
            ),
            (
                "calibration",
                "calibrators/wp14",
                {"method": "identity", "protocol": "wp06-v2"},
            ),
        ):
            ref = self._artifact(namespace, value)
            refs[name] = {
                "id": "wp14-baseline" if name == "model" else "wp14",
                "path": ref["artifact_path"],
                "sha256": ref["sha256"],
            }
        self.store.record_dataset(
            dataset_id="wp14",
            **self._artifact(
                "datasets/wp14", {"fit": "none; fixed WP09-retained baselines"}
            ),
        )
        self.store.record_feature_snapshot(
            feature_snapshot_id="wp14-schema",
            dataset_id="wp14",
            **self._artifact("features/wp14", {"schema": refs["feature_schema"]}),
        )
        self.store.record_model_manifest(
            model_manifest_id="wp14",
            model_id="wp14-baseline",
            model_version_id=1,
            **self._artifact("models/wp14-baseline", model),
        )
        self.store.record_calibrator_manifest(
            calibrator_manifest_id="wp14",
            model_manifest_id="wp14",
            **self._artifact(
                "calibrators/wp14", {"method": "identity", "protocol": "wp06-v2"}
            ),
        )
        self.bundle = {
            "format": "gridoracle-model-bundle-v1",
            **refs,
            "artifacts": list(refs.values()),
            "model_manifest_id": "wp14",
            "dataset_id": "wp14",
            "feature_snapshot_id": "wp14-schema",
            "calibrator_manifest_id": "wp14",
            "code_revision": "WP14 synthetic baseline adapter; not promoted",
            "runtime_image": "test-only source replay; no production image claim",
        }
        self.bundle_path = self.root / "bundle.json"
        self.bundle_path.write_bytes(canonical(self.bundle))
        self.bundle_hash = file_digest(self.bundle_path)
        self.load_model()

    def load_model(self):
        bundle = verify_bundle(
            self.root / "artifacts", self.bundle_path, self.bundle_hash
        )
        verify_selection(self.engine, bundle)
        model = json.loads(
            (self.root / "artifacts" / bundle["model"]["path"]).read_bytes()
        )
        assert (
            model["format"] == "wp14-fixed-baseline-v1" and model["temperature"] == 4.0
        )
        assert model["horizons"] == {
            "pre_weekend": "standings",
            "post_qualifying": "qualifying",
        }
        return model

    def snapshot(self, horizon):
        adapter = ProviderAdapter(
            "wp14-synthetic", "GridOracle offline test", self.root / "provider"
        )
        payload, _ = adapter.fetch_json(
            "https://recorded.invalid/weekend",
            validator=require_keys("entries", "sessions"),
            session=RecordedSession(self.fixture),
        )
        raw = self._artifact(
            "providers/wp14",
            {
                "observed_at": self.now.isoformat(),
                "race_id": self.race_id,
                "payload": payload,
            },
        )
        raw_id = f"{self.race_id}-{horizon}-raw"
        self.store.record_raw_snapshot(
            snapshot_id=raw_id,
            provider="wp14-synthetic",
            retrieved_at=self.now,
            source_available_at=self.now,
            **raw,
        )
        cutoff = self.now.isoformat()
        records = []
        for i, entry in enumerate(payload["entries"], 1):
            row = {
                "race_key": f"{self.season}/1",
                "driver_identity_key": f"entry:{self.race_id * 100 + i}",
                "constructor_identity_key": f"legacy:team:{entry['team']}",
                "horizon": horizon,
                "cutoff": cutoff,
                "driver_championship_position_race_only": entry["standings"],
                "missing__qualifying": horizon == "pre_weekend",
            }
            if horizon == "post_qualifying":
                with self.engine.connect() as conn:
                    # Qualifying position persisted by the real ingestion upsert;
                    # final race grid (including pit lane zero) is never used.
                    row["qualifying_position"] = conn.execute(
                        text(
                            "SELECT grid_position FROM qualifying_results "
                            "WHERE race"
                            "_id=:race AND driver_id=:driver"
                        ),
                        {"race": self.race_id, "driver": i},
                    ).scalar_one()
            records.append(row)
        feature_id = f"{self.race_id}-{horizon}-features"
        self.store.record_feature_snapshot(
            feature_snapshot_id=feature_id,
            dataset_id="wp14",
            **self._artifact("features/wp14", records),
        )
        self.frames[horizon] = pd.DataFrame(records)
        self.inputs[horizon] = ForecastRunInput(
            race_id=self.race_id,
            horizon=horizon,
            input_cutoff_at=self.now,
            issue_at=self.now,
            source_available_at=self.now,
            provenance_grade="observed",
            expected_entry_count=22,
            idempotency_key=f"wp14/{self.race_id}/{horizon}",
            input_manifest={
                "synthetic": True,
                "field_revision": 1,
                "weather": select_weather_for_interval(
                    [],
                    self.event.timestamp("Race"),
                    self.event.timestamp("Race") + timedelta(hours=2),
                ),
            },
            raw_snapshot_id=raw_id,
            dataset_id="wp14",
            feature_snapshot_id=feature_id,
            model_manifest_id="wp14",
            calibrator_manifest_id="wp14",
        )

    def predict(self, horizon, *, persist=True):
        model = self.load_model()
        run_input = self.inputs[horizon]
        # Reload immutable features, so later mutable source/DB changes cannot
        # affect reproduction of an issued forecast.
        with self.engine.connect() as conn:
            path = conn.execute(
                text(
                    "SELECT artifact_path FROM feature_snapshots WHERE featu"
                    "re_snapshot_id=:id"
                ),
                {"id": run_input.feature_snapshot_id},
            ).scalar_one()
        frame = pd.DataFrame(json.loads((self.root / "artifacts" / path).read_bytes()))
        field = Field(
            f"{self.season}/1",
            horizon,
            run_input.input_cutoff_at.isoformat(),
            "1",
            tuple(frame.driver_identity_key),
            teams=tuple(
                zip(
                    frame.driver_identity_key,
                    frame.constructor_identity_key,
                    strict=True,
                )
            ),
        )
        prediction = Baseline(
            model["horizons"][horizon],
            horizon,
            {"model_sha256": self.bundle["model"]["sha256"]},
        ).predict(frame, field)
        self.predictions[horizon] = prediction
        run_id = (
            self.store.create_forecast_run(run_input) if persist else self.runs[horizon]
        )
        outputs = [
            ForecastEntry(
                key,
                {
                    "win_probability": prediction["winner"][key],
                    "rank": prediction["order"].index(key) + 1,
                },
            )
            for key in field.entries
        ]
        if persist:
            self.store.add_entry_outputs(run_id, outputs)
        self.runs[horizon], self.outputs[horizon] = run_id, outputs
        return prediction

    def qualifying(self, _job):
        self.qualifying_calls += 1
        if self.now < time(self.fixture["qualifying_available_at"]):
            raise RetryableJobError("qualifying final source is late")
        qualifying_publication_ready(
            ingested_entries=len(self.fixture["entries"]),
            expected_entries=22,
            grid_verified=True,
        )
        with self.engine.begin() as conn:
            for i, entry in enumerate(self.fixture["entries"], 1):
                upsert_qualifying_result(
                    conn,
                    self.race_id,
                    i,
                    entry["team"],
                    pd.Timedelta(seconds=80 + i),
                    None,
                    None,
                    entry["qualifying"],
                )

    def result(self, _job=None, *, correction=False):
        revision = 2 if correction else 1
        with self.engine.begin() as conn:
            self.result_revision = conn.execute(
                text(
                    "INSERT INTO result_revisions (race_id,revision,source,r"
                    "eason,is_official,recorded_at) VALUES (:race,:rev,'WP14"
                    " synthetic','replay',true,:at) RETURNING id"
                ),
                {"race": self.race_id, "rev": revision, "at": self.now},
            ).scalar_one()
            for i, entry in enumerate(self.fixture["entries"], 1):
                status = (
                    "Disqualified" if correction and i == 1 else entry["status_raw"]
                )
                upsert_race_result(
                    conn,
                    self.race_id,
                    i,
                    entry["team"],
                    entry["grid"],
                    entry["result"],
                    0,
                    status,
                    False,
                    False,
                )
        return self.result_revision

    def evaluate(self, _job=None):
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT driver_id, finish_position, status FROM race_res"
                        "ults WHERE race_id=:race ORDER BY driver_id"
                    ),
                    {"race": self.race_id},
                )
                .mappings()
                .all()
            )
        targets = [
            {
                "driver": f"entry:{self.race_id * 100 + r['driver_id']}",
                "rank": r["finish_position"]
                if classify_result(r["status"], r["finish_position"]).is_target_eligible
                else None,
            }
            for r in rows
        ]
        config = json.loads((ROOT / "docs/benchmark/v2/config.json").read_text())
        for horizon, run_id in self.runs.items():
            scored = score_race(
                targets,
                self.predictions[horizon],
                list(self.predictions[horizon]["winner"]),
                config,
            )
            values = {k: scored[k] for k in SCALARS}
            self.store.record_evaluation(
                evaluation_id=f"{run_id}/{self.result_revision}",
                forecast_run_id=run_id,
                result_revision_id=self.result_revision,
                evaluator_manifest={
                    "public_contract": "wp12-v1",
                    "synthetic": True,
                    "config_sha256": file_digest(
                        ROOT / "docs/benchmark/v2/config.json"
                    ),
                },
                metrics={
                    "values": values,
                    "observations": {k: int(v is not None) for k, v in values.items()},
                },
                evaluated_at=self.now,
            )

    def handlers(self):
        return {
            "pre_weekend.feature": lambda j: self.snapshot("pre_weekend"),
            "pre_weekend.predict": lambda j: self.predict("pre_weekend"),
            "pre_weekend.publish": lambda j: self.store.publish(
                self.runs["pre_weekend"], published_at=self.now
            ),
            "post_qualifying.ingest": self.qualifying,
            "post_qualifying.feature": lambda j: self.snapshot("post_qualifying"),
            "post_qualifying.predict": lambda j: self.predict("post_qualifying"),
            "post_qualifying.publish": lambda j: self.store.publish(
                self.runs["post_qualifying"], published_at=self.now
            ),
            "result.ingest": self.result,
            "result.evaluate": self.evaluate,
        }

    def drain(self):
        for _ in range(30):
            if not self.ledger.run_once("wp14-worker", self.handlers()):
                return
        raise AssertionError("unbounded replay")

    def complete(self):
        self.drain()
        self.now = time(f"{self.season}-05-02T14:45:00+00:00")
        self.drain()
        assert self.qualifying_calls == 1 and "post_qualifying" not in self.runs
        self.now = time(self.fixture["qualifying_available_at"])
        self.drain()
        self.now = time(f"{self.season}-05-03T16:00:00+00:00")
        self.drain()
        return self

    def client(self):
        os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
        from api.database import get_db
        from api.main import create_app

        app = create_app(legacy=False)

        def database():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_db] = database
        return TestClient(app)

    def public(self, horizon="pre_weekend"):
        with self.client() as client:
            response = client.get(
                f"/api/v1/seasons/{self.season}/events/{self.race_id}/forecast?horizon={horizon}"
            )
            assert response.status_code == 200, response.text
            return response.json()

    def hashes(self):
        return inventory(self.engine, self.root / "artifacts")
