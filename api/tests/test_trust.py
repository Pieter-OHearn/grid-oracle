"""Evidence equality, public opt-in, correction and metadata isolation contracts."""

import gzip
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.database import get_db
from api.main import create_app
from api.services.trust import METRICS, metric_projection
from api.tests.public_fixture import build_fixture
from api.tests.test_public import BASE
from scripts.generate_public_performance import OUTPUT, REPORT, projection


@pytest.fixture
def public_db(tmp_path):
    engine, store, ids = build_fixture(
        f"sqlite:///{tmp_path / 'trust.sqlite'}", tmp_path / "artifacts"
    )
    yield engine, store, ids
    engine.dispose()


@pytest.fixture
def public_client(public_db):
    engine, _, _ = public_db
    app = create_app(legacy=False)

    def database():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client


def test_historical_projection_is_exact_stored_evidence(public_client):
    stored = json.loads(gzip.decompress(REPORT.read_bytes()))
    actual = public_client.get("/api/v1/performance/historical")
    assert actual.status_code == 200
    assert actual.json() == json.loads(OUTPUT.read_text()) == projection().model_dump()
    expected_candidates = sum(len(g["candidates"]) for g in stored["horizons"].values())
    assert len(actual.json()["candidates"]) == expected_candidates
    for horizon, group in stored["horizons"].items():
        projected = [c for c in actual.json()["candidates"] if c["horizon"] == horizon]
        assert sum(c["retained"] for c in projected) == 1
        for candidate, source in zip(
            projected, group["candidates"].values(), strict=True
        ):
            assert candidate["expected_races"] == source["summary"]["expected_races"]
            assert candidate["predicted_races"] == source["summary"]["predicted_races"]
            for m in candidate["metrics"]:
                assert m["value"] == source["summary"]["metrics"][m["key"]]
            assert len(candidate["races"]) == len(source["races"]) + len(
                source["missing"]
            )
            for race, original in zip(candidate["races"], source["races"], strict=True):
                assert f"{race['season']}:{race['round']}" == original["race"]
                for key in (
                    "winner_log_loss",
                    "winner_hit",
                    "top3_overlap",
                    "top10_overlap",
                    "rank_mae",
                ):
                    assert race[key] == original[key]
            assert candidate["reliability"] == [
                {k: b[k] for k in candidate["reliability"][0]}
                for b in source["reliability_with_counts"]["winner"]["bins"]
            ]
    assert not any(
        secret in actual.text
        for secret in (
            "artifact_path",
            "sha256",
            "provider:jolpica",
            "coherent_outputs",
            "conditional_top",
        )
    )


def result(conn, revision, race=2022):
    conn.execute(
        text(
            "INSERT INTO result_revisions "
            "(id,race_id,revision,source,reason,is_official) "
            "VALUES (:id,:race,:revision,'private/source','password=secret',true)"
        ),
        {"id": race * 10 + revision, "race": race, "revision": revision},
    )


def test_corrections_are_run_result_bound_and_not_latest_score_fallback(
    public_client, public_db
):
    engine, store, ids = public_db
    with engine.begin() as conn:
        for r in (1, 2, 3):
            result(conn, r)
    for revision, loss in ((1, 0.5), (2, 0.4)):
        store.record_evaluation(
            evaluation_id=f"evaluation{revision}",
            forecast_run_id=ids[(2022, "pre_weekend")],
            result_revision_id=20220 + revision,
            evaluated_at=datetime(2022, 5, 5, tzinfo=UTC),
            evaluator_manifest={"public_contract": "wp12-v1", "private": "secret"},
            metrics={
                "values": {
                    "winner_log_loss": loss,
                    "winner_hit": 0,
                    "private": "secret",
                },
                "observations": {"winner_log_loss": 1, "winner_hit": 1},
            },
        )
    data = public_client.get(BASE + "/performance?horizon=pre_weekend").json()
    assert data["run_id"] == ids[(2022, "pre_weekend")]
    assert [c["revision"] for c in data["corrections"]] == [1, 2, 3]
    for c, value in zip(data["corrections"], (0.5, 0.4), strict=False):
        e = c["evaluations"][0]
        assert e["result_revision"] == c["revision"]
        assert e["run_id"] == data["run_id"]
        assert e["metrics"][0]["value"] == value
        assert e["metrics"][1]["value"] == 0
        assert e["metrics"][2]["value"] is None
    assert data["corrections"][-1]["evaluations"] == []
    assert "secret" not in str(data) and "private" not in str(data)
    absent = public_client.get(BASE + "/performance?horizon=post_qualifying").json()
    assert absent["status"] == "no_published_forecast"
    assert all(c["evaluations"] == [] for c in absent["corrections"])


def test_legacy_and_unpublished_evaluations_are_withheld(public_client, public_db):
    engine, store, ids = public_db
    with engine.begin() as conn:
        result(conn, 1)
    for horizon in ("pre_weekend", "post_qualifying"):
        store.record_evaluation(
            evaluation_id=horizon,
            forecast_run_id=ids[(2022, horizon)],
            result_revision_id=20221,
            evaluated_at=datetime(2022, 5, 5, tzinfo=UTC),
            evaluator_manifest={},
            metrics={"winner_log_loss": 0.001},
        )
    data = public_client.get(
        "/api/v1/seasons/2022/performance?horizon=pre_weekend"
    ).json()
    assert data["events"][0]["status"] == "evaluation_unavailable"
    assert data["events"][0]["corrections"][0]["evaluations"] == []
    assert (
        public_client.get(
            "/api/v1/seasons/2026/events/2022/performance?horizon=pre_weekend"
        ).status_code
        == 404
    )


@pytest.mark.parametrize("value", [True, float("nan"), -1, "0.5", 1.2])
def test_invalid_stored_fraction_never_becomes_public_accuracy(value):
    with pytest.raises(Exception, match="Stored evaluation is invalid"):
        metric_projection({"winner_hit": value}, {"winner_hit": 1})


def test_denominators_and_missing_outcomes_remain_unavailable():
    metrics = metric_projection(
        {"winner_hit": 0.8, "top3_overlap": 0}, {"top3_overlap": 1}
    )
    assert metrics[1].value is None
    assert next(m for m in metrics if m.key == "top3_overlap").value == 0
    assert len(metrics) == len(METRICS)
