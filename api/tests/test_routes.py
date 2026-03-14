import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, get_db
from api.main import app
from api.models.orm import (
    Circuit,
    Constructor,
    Driver,
    EvaluationMetrics,
    ModelVersion,
    Prediction,
    Race,
    RaceResult,
)

DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seed_data(db):
    circuit = Circuit(
        name="Bahrain International Circuit",
        country="Bahrain",
        city="Sakhir",
        circuit_type="permanent",
        total_laps=57,
        length_km=5.412,
    )
    db.add(circuit)
    db.flush()

    race = Race(
        season=2024,
        round=1,
        name="Bahrain Grand Prix",
        circuit_id=circuit.id,
        date=datetime.date(2024, 3, 2),
        is_completed=True,
    )
    db.add(race)
    db.flush()

    driver1 = Driver(code="VER", full_name="Max Verstappen", nationality="Dutch")
    driver2 = Driver(code="PER", full_name="Sergio Perez", nationality="Mexican")
    db.add_all([driver1, driver2])
    db.flush()

    constructor = Constructor(
        name="Red Bull Racing", nationality="Austrian", color_hex="#3671C6"
    )
    db.add(constructor)
    db.flush()

    model_version = ModelVersion(
        name="xgb_v1",
        trained_at=datetime.datetime(2024, 3, 1, 12, 0, tzinfo=datetime.timezone.utc),
        training_races_count=10,
    )
    db.add(model_version)
    db.flush()

    pred1 = Prediction(
        race_id=race.id,
        model_version_id=model_version.id,
        driver_id=driver1.id,
        constructor_id=constructor.id,
        predicted_position=1,
        confidence_score=0.9500,
        created_at=datetime.datetime(2024, 3, 1, 12, 0, tzinfo=datetime.timezone.utc),
    )
    pred2 = Prediction(
        race_id=race.id,
        model_version_id=model_version.id,
        driver_id=driver2.id,
        constructor_id=constructor.id,
        predicted_position=2,
        confidence_score=0.7000,
        created_at=datetime.datetime(2024, 3, 1, 12, 0, tzinfo=datetime.timezone.utc),
    )
    db.add_all([pred1, pred2])

    result1 = RaceResult(
        race_id=race.id,
        driver_id=driver1.id,
        constructor_id=constructor.id,
        grid_position=1,
        finish_position=1,
        status="Finished",
    )
    result2 = RaceResult(
        race_id=race.id,
        driver_id=driver2.id,
        constructor_id=constructor.id,
        grid_position=2,
        finish_position=2,
        status="Finished",
    )
    db.add_all([result1, result2])

    metrics = EvaluationMetrics(
        race_id=race.id,
        model_version_id=model_version.id,
        evaluated_at=datetime.datetime(2024, 3, 3, 10, 0, tzinfo=datetime.timezone.utc),
        top3_accuracy=1.0000,
        exact_position_accuracy=1.0000,
        mean_position_error=0.0000,
    )
    db.add(metrics)
    db.commit()

    return {"race_id": race.id, "season": 2024}


# --- /races/{season} ---

def test_list_races_returns_200(client, seed_data):
    response = client.get(f"/races/{seed_data['season']}")
    assert response.status_code == 200


def test_list_races_returns_race(client, seed_data):
    response = client.get(f"/races/{seed_data['season']}")
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Bahrain Grand Prix"
    assert data[0]["circuit"] == "Bahrain International Circuit"
    assert data[0]["is_completed"] is True


def test_list_races_empty_season(client, seed_data):
    response = client.get("/races/1900")
    assert response.status_code == 200
    assert response.json() == []


# --- /races/{race_id}/predictions ---

def test_get_predictions_returns_200(client, seed_data):
    response = client.get(f"/races/{seed_data['race_id']}/predictions")
    assert response.status_code == 200


def test_get_predictions_ordered_by_position(client, seed_data):
    response = client.get(f"/races/{seed_data['race_id']}/predictions")
    data = response.json()
    positions = [item["predicted_position"] for item in data]
    assert positions == sorted(positions)


def test_get_predictions_contains_expected_fields(client, seed_data):
    response = client.get(f"/races/{seed_data['race_id']}/predictions")
    item = response.json()[0]
    assert "driver" in item
    assert "constructor" in item
    assert "predicted_position" in item
    assert "confidence_score" in item


def test_get_predictions_404_unknown_race(client, seed_data):
    response = client.get("/races/99999/predictions")
    assert response.status_code == 404


def test_get_predictions_404_no_predictions(client, db, seed_data):
    # Add a race without predictions
    circuit = db.query(Circuit).first()
    race2 = Race(
        season=2024,
        round=2,
        name="Saudi Arabian Grand Prix",
        circuit_id=circuit.id,
        date=datetime.date(2024, 3, 9),
        is_completed=False,
    )
    db.add(race2)
    db.commit()

    response = client.get(f"/races/{race2.id}/predictions")
    assert response.status_code == 404


# --- /races/{race_id}/results ---

def test_get_results_returns_200(client, seed_data):
    response = client.get(f"/races/{seed_data['race_id']}/results")
    assert response.status_code == 200


def test_get_results_contains_expected_fields(client, seed_data):
    response = client.get(f"/races/{seed_data['race_id']}/results")
    item = response.json()[0]
    assert "driver" in item
    assert "constructor" in item
    assert "finish_position" in item
    assert "grid_position" in item
    assert "status" in item


def test_get_results_404_unknown_race(client, seed_data):
    response = client.get("/races/99999/results")
    assert response.status_code == 404


def test_get_results_404_no_results(client, db, seed_data):
    circuit = db.query(Circuit).first()
    race2 = Race(
        season=2024,
        round=2,
        name="Saudi Arabian Grand Prix",
        circuit_id=circuit.id,
        date=datetime.date(2024, 3, 9),
        is_completed=False,
    )
    db.add(race2)
    db.commit()

    response = client.get(f"/races/{race2.id}/results")
    assert response.status_code == 404


# --- /races/{race_id}/comparison ---

def test_get_comparison_returns_200(client, seed_data):
    response = client.get(f"/races/{seed_data['race_id']}/comparison")
    assert response.status_code == 200


def test_get_comparison_contains_delta(client, seed_data):
    response = client.get(f"/races/{seed_data['race_id']}/comparison")
    data = response.json()
    for item in data:
        assert "position_delta" in item
        # Both predictions and results exist so delta should not be None
        assert item["position_delta"] is not None


def test_get_comparison_delta_values(client, seed_data):
    response = client.get(f"/races/{seed_data['race_id']}/comparison")
    data = response.json()
    # predicted 1 → finished 1, predicted 2 → finished 2: both deltas == 0
    deltas = [item["position_delta"] for item in data]
    assert all(d == 0 for d in deltas)


def test_get_comparison_404_unknown_race(client, seed_data):
    response = client.get("/races/99999/comparison")
    assert response.status_code == 404


# --- /seasons/{season}/accuracy ---

def test_get_season_accuracy_returns_200(client, seed_data):
    response = client.get(f"/seasons/{seed_data['season']}/accuracy")
    assert response.status_code == 200


def test_get_season_accuracy_contains_metrics(client, seed_data):
    response = client.get(f"/seasons/{seed_data['season']}/accuracy")
    data = response.json()
    assert len(data) == 1
    item = data[0]
    assert item["race_name"] == "Bahrain Grand Prix"
    assert item["top3_accuracy"] == 1.0
    assert item["exact_position_accuracy"] == 1.0
    assert item["mean_position_error"] == 0.0


def test_get_season_accuracy_empty_season(client, seed_data):
    response = client.get("/seasons/1900/accuracy")
    assert response.status_code == 200
    assert response.json() == []
