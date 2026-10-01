"""Explicit synthetic WP11 acceptance DB. Never called by app/startup/imports."""

import argparse
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from api.database import Base
from api.models.orm import Circuit, Constructor, Driver, ModelVersion, Race
from gridoracle.provenance import (
    ContentAddressedArtifactStore,
    ForecastEntry,
    ForecastRunInput,
    ImmutableProvenanceStore,
)
from scripts.db_migrate import LEGACY_CORE_TABLES, upgrade_database


def build_fixture(
    database_url: str,
    artifact_dir: Path,
    *,
    probabilities=None,
    horizon_probabilities=None,
):
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False}
        if database_url.startswith("sqlite:")
        else {},
    )
    if inspect(engine).get_table_names():
        raise ValueError("Fixture builder refuses a non-empty database")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table in sorted(
            LEGACY_CORE_TABLES - set(inspect(engine).get_table_names())
        ):
            conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
    with Session(engine) as db:
        circuit = Circuit(
            name="Current circuit name MUST NOT leak",
            country="Fixture",
            city="Fixture",
            circuit_type="permanent",
            total_laps=50,
            length_km=5,
        )
        team = Constructor(
            name="Current brand MUST NOT leak",
            nationality="Fixture",
            color_hex="#ff0000",
        )
        drivers = [
            Driver(
                code=f"F{i:02}", full_name=f"Current roster {i}", nationality="Fixture"
            )
            for i in range(1, 23)
        ]
        model = ModelVersion(
            name="private-model",
            trained_at=datetime(2022, 1, 1),
            training_races_count=10,
            artifact_path="/private/model/secret",
        )
        db.add_all([circuit, team, model, *drivers])
        db.flush()
        db.add_all(
            [
                Race(
                    id=year,
                    season=year,
                    round=1,
                    name=f"{year} Grand Prix · synthetic acceptance fixture",
                    circuit_id=circuit.id,
                    date=date(year, 5, 4),
                    is_completed=True,
                )
                for year in (2022, 2026)
            ]
        )
        db.commit()
    upgrade_database(database_url)
    with engine.begin() as conn:
        for year in (2022, 2026):
            conn.execute(
                text(
                    "INSERT INTO season_rulesets "
                    "(season,ruleset_version,source,is_current,payload) VALUES "
                    "(:year,'2026.1','synthetic fixture',true,'{}')"
                ),
                {"year": year},
            )
            for kind, key in [
                ("team", "legacy:team:1"),
                ("circuit", "legacy:circuit:1"),
            ]:
                conn.execute(
                    text(
                        "INSERT INTO entity_aliases "
                        "(entity_kind,identity_key,provider,provider_key,"
                        "valid_from,valid_to,is_display_alias) "
                        "VALUES (:kind,:key,'fixture',:name,:start,:end,true)"
                    ),
                    {
                        "kind": kind,
                        "key": key,
                        "name": f"Fixture {kind} {year}",
                        "start": f"{year}-01-01",
                        "end": f"{year + 1}-01-01",
                    },
                )
            for driver in range(1, 23):
                conn.execute(
                    text(
                        "INSERT INTO entity_aliases "
                        "(entity_kind,identity_key,provider,provider_key,"
                        "valid_from,valid_to,is_display_alias) "
                        "VALUES ('driver',:key,'fixture',:name,:start,:end,true)"
                    ),
                    {
                        "key": f"legacy:driver:{driver}",
                        "name": f"Fixture Driver {driver:02} · {year}",
                        "start": f"{year}-01-01",
                        "end": f"{year + 1}-01-01",
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO event_entries "
                        "(id,race_id,driver_id,constructor_id,role,status,revision) "
                        "VALUES "
                        "(:id,:year,:driver,1,'primary','active',1)"
                    ),
                    {"id": year * 100 + driver, "year": year, "driver": driver},
                )
            for revision in (1, 2):
                conn.execute(
                    text(
                        "INSERT INTO event_sessions "
                        "(race_id,kind,scheduled_at,revision,status) VALUES "
                        "(:year,'race',:time,:revision,'completed')"
                    ),
                    {
                        "year": year,
                        "time": f"{year}-05-04T14:00:00+00:00",
                        "revision": revision,
                    },
                )
            conn.execute(
                text(
                    "INSERT INTO event_sessions "
                    "(race_id,kind,scheduled_at,revision,status) VALUES "
                    "(:year,'qualifying',:time,1,'completed')"
                ),
                {"year": year, "time": f"{year}-05-03T14:00:00+00:00"},
            )
    store = ImmutableProvenanceStore(
        engine, ContentAddressedArtifactStore(artifact_dir)
    )

    def artifact(namespace, content):
        a = store.artifacts.put_bytes(namespace, content)
        return {
            "artifact_path": a.path,
            "sha256": a.sha256,
            "manifest": {"private": "never public"},
        }

    store.record_raw_snapshot(
        snapshot_id="raw",
        provider="fixture",
        retrieved_at=datetime(2022, 5, 1, tzinfo=UTC),
        source_available_at=datetime(2022, 5, 1, tzinfo=UTC),
        **artifact("providers/fixture", b"raw"),
    )
    store.record_dataset(dataset_id="dataset", **artifact("datasets/fixture", b"data"))
    store.record_feature_snapshot(
        feature_snapshot_id="features",
        dataset_id="dataset",
        **artifact("features/fixture", b"features"),
    )
    store.record_model_manifest(
        model_manifest_id="model",
        model_id="fixture",
        model_version_id=1,
        **artifact("models/fixture", b"model"),
    )
    store.record_calibrator_manifest(
        calibrator_manifest_id="calibrator",
        model_manifest_id="model",
        **artifact("calibrators/fixture", b"calibrator"),
    )
    run_ids = {}
    for year in (2022, 2026):
        issued = datetime(year, 5, 1, tzinfo=UTC)
        for horizon in ("pre_weekend", "post_qualifying"):
            if horizon_probabilities and horizon == "post_qualifying":
                issued = datetime(year, 5, 3, 18, tzinfo=UTC)
            run_id = store.create_forecast_run(
                ForecastRunInput(
                    race_id=year,
                    horizon=horizon,
                    input_cutoff_at=issued - timedelta(hours=1),
                    issue_at=issued,
                    source_available_at=issued - timedelta(hours=2),
                    provenance_grade="verified",
                    expected_entry_count=22,
                    idempotency_key=f"{year}/{horizon}",
                    input_manifest={"private": "never public"},
                    raw_snapshot_id="raw",
                    dataset_id="dataset",
                    feature_snapshot_id="features",
                    model_manifest_id="model",
                    calibrator_manifest_id="calibrator",
                )
            )
            values = probabilities if probabilities is not None else [1 / 22] * 22
            if horizon_probabilities is not None:
                values = horizon_probabilities[horizon]
            store.add_entry_outputs(
                run_id,
                [
                    ForecastEntry(
                        f"entry:{year * 100 + i}",
                        {
                            "win_probability": values[i - 1],
                            "internal_secret": "never public",
                            "rank": i,
                        },
                    )
                    for i in range(1, 23)
                ],
            )
            # Only one horizon approved: the other deliberately stays unpublished.
            if horizon == "pre_weekend":
                store.publish(run_id, published_at=issued)
            run_ids[(year, horizon)] = run_id
    return engine, store, run_ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    engine, _, _ = build_fixture(
        f"sqlite:///{args.database}", args.database.parent / "wp11-fixture-artifacts"
    )
    engine.dispose()
