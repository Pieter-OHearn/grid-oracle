"""Production issuance: provider reads, schedule, features and targets."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
import requests

from pipeline.benchmark.temporal import validate_features
from pipeline.dataset.historical import DatasetBackfill
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
from pipeline.issuance.jolpica import JolpicaClient
from pipeline.orchestration import JobLedger, weekend_graph
from pipeline.selection.interface import Baseline
from pipeline.selection.outputs import Field
from pipeline.tests.jolpica_fixture import FakeJolpica, recorded

AFTER_ROUND_2 = datetime(2026, 3, 26, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def no_provider_network(monkeypatch):
    def deny(*_args, **_kwargs):
        raise AssertionError("live provider network is forbidden in tests")

    monkeypatch.setattr(requests.sessions.Session, "request", deny)


def client(tmp_path, now=AFTER_ROUND_2):
    session = FakeJolpica(lambda: now)
    return JolpicaClient(tmp_path / "provider", session=session, now=lambda: now), session


def test_season_results_are_read_page_by_page_and_merged_per_race(tmp_path):
    jolpica, session = client(tmp_path, datetime(2026, 3, 30, tzinfo=UTC))
    observation = jolpica.results(2026)
    races = observation.races()
    assert [race["round"] for race in races] == ["1", "2", "3"]
    assert [len(race["Results"]) for race in races] == [22, 22, 22]
    # 66 rows in pages of 100 is one page; the schedule is one page too.
    assert [params["offset"] for _, params in session.calls] == [0]
    assert observation.document()["payload"] == observation.payload
    assert observation.retrieved_at == datetime(2026, 3, 30, tzinfo=UTC)


def test_pagination_follows_the_provider_total(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.issuance.jolpica.PAGE", 30)
    jolpica, session = client(tmp_path, datetime(2026, 3, 30, tzinfo=UTC))
    races = jolpica.results(2026).races()
    assert [params["offset"] for _, params in session.calls] == [0, 30, 60]
    assert [len(race["Results"]) for race in races] == [22, 22, 22]
    flat = [row["Driver"]["driverId"] for race in races for row in race["Results"]]
    expected = [
        row["Driver"]["driverId"]
        for key in ("1", "2", "3")
        for row in recorded()["results"][key]["MRData"]["RaceTable"]["Races"][0]["Results"]
    ]
    assert flat == expected


def test_schedule_maps_sessions_and_sprint_weekends():
    events = domain.parse_schedule(recorded()["schedule"]["MRData"]["RaceTable"]["Races"])
    assert len(events) == 23
    china, japan = events[1], events[2]
    assert set(china.sessions) == {"practice_1", "sprint_qualifying", "sprint", "qualifying", "race"}
    assert set(japan.sessions) == {"practice_1", "practice_2", "practice_3", "qualifying", "race"}
    assert japan.race_start == datetime(2026, 3, 29, 5, tzinfo=UTC)
    names = {domain.NAMES[kind] for kind in china.sessions}
    assert names == {"Practice 1", "Sprint Qualifying", "Sprint", "Qualifying", "Race"}


def test_a_sprint_shootout_never_unlocks_post_qualifying():
    china = domain.parse_schedule(recorded()["schedule"]["MRData"]["RaceTable"]["Races"])[1]
    from pipeline.orchestration import EventSchedule

    schedule = EventSchedule(
        race_id=2,
        season=2026,
        round_number=2,
        sessions={domain.NAMES[kind]: at for kind, at in china.sessions.items()},
        expected_entries=22,
    )
    graph = {job.kind: job for job in weekend_graph(schedule)}
    # The pre-weekend cutoff is before sprint qualifying, the first competitive
    # session; post-qualifying waits for Grand Prix qualifying.
    assert graph["pre_weekend.publish"].payload["pre_cutoff"] == "2026-03-13T07:29:00+00:00"
    assert graph["post_qualifying.ingest"].due_at == datetime(2026, 3, 14, 7, 45, tzinfo=UTC)


def test_race_only_standings_match_the_wp05_dataset_ranks():
    races = [recorded()["results"][key]["MRData"]["RaceTable"]["Races"][0] for key in ("1", "2", "3")]
    drivers = [row["Driver"]["driverId"] for row in races[1]["Results"]] + ["newcomer"]
    standings = race_standings(races, 2026, 3, drivers)
    # Round 3's own points never count toward its standings.
    totals: dict[str, float] = {}
    for race in races[:2]:
        for row in race["Results"]:
            driver = row["Driver"]["driverId"]
            totals[driver] = totals.get(driver, 0.0) + float(row["points"])
    leader = max(totals, key=lambda driver: (totals[driver], driver))
    assert standings[leader] == 1
    frame = pd.DataFrame(
        [
            {
                "season": 2026,
                "round": int(race["round"]),
                "driver": row["Driver"]["driverId"],
                "points": float(row["points"]),
            }
            for race in races[:2]
            for row in race["Results"]
        ]
        + [{"season": 2026, "round": 3, "driver": driver, "points": 0.0} for driver in sorted(set(drivers))]
    )
    reference = DatasetBackfill._standings(frame, "driver")[frame["round"] == 3]
    assert standings == dict(zip(frame.loc[frame["round"] == 3, "driver"], reference, strict=True))
    # A driver with no earlier race ranks after everyone who has one.
    assert standings["newcomer"] == len(totals) + 1


def _field(race):
    return [
        {
            "key": f"entry:{index}",
            "driver": row["Driver"]["driverId"],
            "team_key": domain.identity("team", row["Constructor"]["constructorId"]),
            "provenance": "previous_round_classification",
        }
        for index, row in enumerate(race["Results"], start=100)
    ]


@pytest.mark.parametrize("horizon", [PRE_WEEKEND, POST_QUALIFYING])
def test_baseline_forecast_from_production_features(horizon):
    data = recorded()
    races = [data["results"][key]["MRData"]["RaceTable"]["Races"][0] for key in ("1", "2")]
    entries = _field(races[1])
    standings = race_standings(races, 2026, 3, [entry["driver"] for entry in entries])
    qualifying_race = data["qualifying"]["3"]["MRData"]["RaceTable"]["Races"][0]
    cutoff = "2026-03-27T06:00:00+00:00"
    records = feature_records(
        season=2026,
        round_number=3,
        horizon=horizon,
        cutoff=cutoff,
        entries=entries,
        standings=standings,
        qualifying=qualifying_positions(qualifying_race) if horizon == POST_QUALIFYING else None,
    )
    frame = pd.DataFrame(records)
    validate_features(frame, horizon)
    field = Field(
        "2026/3",
        horizon,
        cutoff,
        "test",
        tuple(frame.driver_identity_key),
        teams=tuple(zip(frame.driver_identity_key, frame.constructor_identity_key, strict=True)),
    )
    name = "standings" if horizon == PRE_WEEKEND else "qualifying"
    prediction = Baseline(name, horizon, {"model_sha256": "0" * 64}).predict(frame, field)
    assert abs(sum(prediction["winner"].values()) - 1) < 1e-12
    assert len(prediction["order"]) == 22
    if horizon == POST_QUALIFYING:
        pole = min(records, key=lambda row: row["qualifying_position"] or 99)
        assert prediction["order"][0] == pole["driver_identity_key"]
    else:
        assert all(row["missing__qualifying"] for row in records)


def test_qualifying_is_verified_only_when_positions_are_contiguous():
    race = recorded()["qualifying"]["3"]["MRData"]["RaceTable"]["Races"][0]
    assert qualifying_verified(race)
    without_pole = [row for row in race["QualifyingResults"] if row["position"] != "1"]
    assert not qualifying_verified({**race, "QualifyingResults": without_pole})
    assert not qualifying_verified({"QualifyingResults": []})


def test_targets_use_contiguous_internal_ranks_over_the_field():
    race = recorded()["results"]["3"]["MRData"]["RaceTable"]["Races"][0]
    rows = race["Results"]
    field = {f"entry:{i}": row["Driver"]["driverId"] for i, row in enumerate(rows[:5])}
    field["entry:absent"] = "not-entered"
    cohort, outside = targets(field, race)
    ranks = {item["driver"]: item["rank"] for item in cohort}
    assert ranks["entry:absent"] is None
    eligible = sorted(rank for rank in ranks.values() if rank is not None)
    assert eligible == list(range(1, len(eligible) + 1))
    assert outside == len(rows) - 5


def test_run_once_takes_a_retry_budget(tmp_path):
    from scripts.db_migrate import LEGACY_CORE_TABLES, upgrade_database
    from sqlalchemy import create_engine

    url = f"sqlite:///{tmp_path / 'ledger.sqlite'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        from sqlalchemy import text

        for table in sorted(LEGACY_CORE_TABLES):
            conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
    upgrade_database(url)
    now = datetime(2026, 3, 27, 6, tzinfo=UTC)
    clock = {"now": now}
    ledger = JobLedger(engine, now=lambda: clock["now"])
    from pipeline.orchestration import EventSchedule, RetryableJobError

    ledger.reconcile(
        EventSchedule(
            race_id=3,
            season=2026,
            round_number=3,
            sessions={"Qualifying": datetime(2026, 3, 28, 6, tzinfo=UTC), "Race": datetime(2026, 3, 29, 5, tzinfo=UTC)},
            expected_entries=22,
        )
    )

    def late(_job):
        raise RetryableJobError("not yet")

    handlers = {kind: late for kind in ("pre_weekend.feature",)}
    for _ in range(13):
        assert ledger.run_once("w", handlers, max_attempts=40)
        with engine.connect() as conn:
            status, due = conn.execute(
                text("SELECT status, due_at FROM orchestration_jobs WHERE kind='pre_weekend.feature'")
            ).one()
        assert status == "pending"
        clock["now"] = datetime.fromisoformat(str(due)).replace(tzinfo=UTC)
    engine.dispose()


def test_backup_status_becomes_prometheus_rows(tmp_path):
    from gridoracle.ops.backup import backup_metrics, healthy

    status = tmp_path / "status" / "status.json"
    status.parent.mkdir()
    status.write_text(
        '{"last_success_at": "2026-10-09T02:00:00+00:00", "last_attempt_ok": true, '
        '"verified_sets": 2, "failed_sets": 0, "last_bytes": 1234}'
    )
    rows = backup_metrics(str(status))
    assert "gridoracle_backup_status_present 1" in rows
    assert "gridoracle_backup_verified_sets 2" in rows
    assert "gridoracle_backup_failed_sets 0" in rows
    stamp = datetime(2026, 10, 9, 2, tzinfo=UTC).timestamp()
    assert f"gridoracle_backup_last_success_timestamp_seconds {stamp}" in rows
    assert healthy(tmp_path, datetime(2026, 10, 10, 3, tzinfo=UTC))
    assert not healthy(tmp_path, datetime(2026, 10, 10, 5, tzinfo=UTC))
    assert backup_metrics(None) == []
    status.write_text("not json")
    assert backup_metrics(str(status))[-1] == "gridoracle_backup_status_present 0"
    assert not healthy(tmp_path / "missing")


def test_role_urls_must_name_plain_roles_with_passwords():
    from gridoracle.ops.roles import _identity

    assert _identity("postgresql://gridoracle_api:pw@db:5432/gridoracle") == ("gridoracle_api", "pw")
    for url in (
        'postgresql://"x;drop":pw@db/gridoracle',
        "postgresql://Api:pw@db/gridoracle",
        "postgresql://gridoracle_api@db/gridoracle",
    ):
        with pytest.raises(ValueError):
            _identity(url)


def test_a_set_is_made_readable_by_the_platform_backup_user(tmp_path):
    from gridoracle.ops.backup import publishable
    from gridoracle.provenance import ContentAddressedArtifactStore

    store = ContentAddressedArtifactStore(tmp_path / "set" / "artifacts")
    ref = store.put_bytes("models/example", b"model")
    stored = tmp_path / "set" / "artifacts" / ref.path
    # The artifact store writes through mkstemp, so files start owner-only.
    assert stored.stat().st_mode & 0o777 == 0o600
    (tmp_path / "set" / "private").mkdir(mode=0o700)
    publishable(tmp_path / "set")
    for path in [tmp_path / "set", *(tmp_path / "set").rglob("*")]:
        assert path.stat().st_mode & 0o777 == (0o755 if path.is_dir() else 0o644), path
