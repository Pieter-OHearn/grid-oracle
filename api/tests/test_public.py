"""WP11 contracts, publication isolation and historical-context regressions."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from api.database import get_db
from api.main import create_app
from api.services.public import _freshness
from api.tests.public_fixture import build_fixture


@pytest.fixture
def public_db(tmp_path):
    engine, store, ids = build_fixture(
        f"sqlite:///{tmp_path / 'public.sqlite'}", tmp_path / "artifacts"
    )
    yield engine, store, ids
    engine.dispose()


@pytest.fixture
def public_client(public_db):
    engine, _, _ = public_db
    application = create_app(legacy=False)

    def database():
        with Session(engine) as session:
            yield session

    application.dependency_overrides[get_db] = database
    with TestClient(application) as client:
        yield client


BASE = "/api/v1/seasons/2022/events/2022"


def test_resources_and_revision_selection(public_client):
    assert [
        s["year"] for s in public_client.get("/api/v1/seasons").json()["seasons"]
    ] == [2026, 2022]
    assert (
        public_client.get("/api/v1/seasons/2022").json()["ruleset_version"] == "2026.1"
    )
    event = public_client.get(BASE).json()
    assert event["circuit_name"] == "Fixture circuit 2022"
    assert event["coverage"]["available"] == 1
    assert public_client.get("/api/v1/seasons/2022/events").json()["events"][0] == event
    sessions = public_client.get(BASE + "/sessions").json()["sessions"]
    assert len(sessions) == 2
    assert next(s for s in sessions if s["kind"] == "race")["revision"] == 2


def test_publication_only_full_field_and_historical_branding(public_client, public_db):
    _, _, ids = public_db
    selection = public_client.get(BASE + "/forecast?horizon=pre_weekend").json()
    assert selection["state"] == "published"
    run = selection["run"]
    assert run["run_id"] == ids[(2022, "pre_weekend")]
    assert len(run["entries"]) == 22
    assert run["entries"][0]["driver_name"].endswith("2022")
    assert run["entries"][0]["team_name"] == "Fixture team 2022"
    assert run["entries"][0]["team_color"] is None
    assert "Current" not in str(run)
    assert "private" not in str(run) and "internal_secret" not in str(run)
    assert run["freshness"]["state"] == "verified_as_of_cutoff"
    assert public_client.get(BASE + "/runs").json()["runs"] == [run]
    assert (
        public_client.get(BASE + "/runs/" + ids[(2022, "post_qualifying")]).status_code
        == 404
    )
    assert public_client.get(BASE + "/runs/" + ids[(2022, "pre_weekend")]).json() == run
    assert (
        public_client.get(
            "/api/v1/seasons/2026/events/2026/forecast?horizon=pre_weekend"
        ).json()["run"]["entries"][0]["team_name"]
        == "Fixture team 2026"
    )


def test_absence_is_not_error_and_scope_is_enforced(public_client):
    absent = public_client.get(BASE + "/forecast?horizon=post_qualifying")
    assert absent.status_code == 200
    assert absent.json() == {
        "state": "unavailable",
        "reason": "no_published_forecast",
        "run": None,
    }
    assert public_client.get("/api/v1/seasons/2026/events/2022").status_code == 404
    assert (
        public_client.get(BASE + "/forecast?horizon=unknown").json()["error"]["code"]
        == "invalid_request"
    )
    assert public_client.get("/api/v1/legacy/races/2022").json()["season"] == 2022
    assert public_client.get("/api/v1/legacy/races/999").status_code == 404


def test_no_internal_or_mutating_public_routes(public_client):
    paths = public_client.get("/openapi.json").json()["paths"]
    assert not any(
        "model-version" in p or "prediction" in p or "accuracy" in p for p in paths
    )
    assert all(set(resource) == {"get"} for resource in paths.values())
    assert public_client.get("/model-versions?season=2022").status_code == 404
    for method in ("post", "put", "patch", "delete"):
        assert getattr(public_client, method)(BASE + "/runs").status_code == 405


def test_database_failure_is_sanitized_and_retryable():
    application = create_app(legacy=False)

    def failed_db():
        raise OperationalError("password=secret /private/path", {}, Exception("secret"))

    application.dependency_overrides[get_db] = failed_db
    with TestClient(application) as client:
        response = client.get("/api/v1/seasons")
    assert response.status_code == 503
    assert response.json()["error"]["retryable"] is True
    assert response.json()["error"]["code"] == "api_unavailable"
    assert "secret" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_empty_season_and_missing_aliases(public_client, public_db):
    engine, _, _ = public_db
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO season_rulesets "
                "(season,ruleset_version,source,is_current,payload) VALUES "
                "(2020,'2026.1','fixture',true,'{}')"
            )
        )
        conn.execute(text("DELETE FROM entity_aliases WHERE entity_kind = 'team'"))
    assert public_client.get("/api/v1/seasons/2020/events").json()["events"] == []
    entries = public_client.get(BASE + "/forecast?horizon=pre_weekend").json()["run"][
        "entries"
    ]
    assert all(e["team_name"] is None for e in entries)


@pytest.mark.parametrize("value", [None, 0, -1, 1.1, True, "0.2"])
def test_output_validation_and_null_semantics(tmp_path, value):
    engine, _, _ = build_fixture(
        f"sqlite:///{tmp_path / 'null.sqlite'}",
        tmp_path / "artifacts",
        probabilities=[value] + [1 / 22] * 21,
    )
    application = create_app(legacy=False)

    def database():
        with Session(engine) as db:
            yield db

    application.dependency_overrides[get_db] = database
    with TestClient(application) as client:
        response = client.get(BASE + "/forecast?horizon=pre_weekend")
    if value is None or (type(value) is int and value == 0):
        assert response.status_code == 200
        entry = response.json()["run"]["entries"][0]
        assert entry["win_probability"] == value
    else:
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "invalid_publication"
    engine.dispose()


def test_freshness_never_means_current_wall_clock():
    data = {
        "input_cutoff_at": "2022-05-01T10:00:00Z",
        "issue_at": "2022-05-01T11:00:00Z",
        "source_available_at": "2022-05-01T09:00:00Z",
        "provenance_grade": "observed",
    }
    assert _freshness(data).state == "unknown"
    data["source_available_at"] = "2022-05-01T12:00:00Z"
    assert _freshness(data).state == "source_late"
    data["input_cutoff_at"] = None
    assert _freshness(data).state == "unknown"
