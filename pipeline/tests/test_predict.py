"""Unit tests for pipeline.ml.predict."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from pipeline.ml.features import prepare_features
from pipeline.ml.predict import (
    load_features,
    load_model,
    normalise_positions,
    run,
    store_predictions,
)
from pipeline.ml.train import FEATURE_COLS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature_data() -> dict:
    """Return a single feature_data dict matching FEATURE_COLS."""
    rng = np.random.RandomState(42)
    return {
        "grid_position": int(rng.randint(1, 21)),
        "driver_avg_position_last_3_races": float(rng.uniform(1, 20)),
        "driver_avg_position_at_circuit": float(rng.uniform(1, 20)),
        "driver_podium_rate_at_circuit": float(rng.uniform(0, 1)),
        "constructor_avg_position_last_3_races": float(rng.uniform(1, 20)),
        "constructor_avg_position_at_circuit": float(rng.uniform(1, 20)),
        "circuit_type": rng.choice(["street", "road", "high-speed"]),
        "is_wet_race_forecast": bool(rng.choice([True, False])),
        "driver_wet_race_avg_position": float(rng.uniform(1, 20)),
        "constructor_wet_race_avg_position": float(rng.uniform(1, 20)),
        "driver_season_avg_position": float(rng.uniform(1, 20)),
        "championship_position": int(rng.randint(1, 21)),
    }


def _make_features_df(n: int = 5) -> pd.DataFrame:
    """Create a DataFrame mimicking the output of load_features."""
    rows = []
    for i in range(n):
        fd = _make_feature_data()
        fd["driver_id"] = i + 1
        fd["constructor_id"] = (i % 5) + 1
        rows.append(fd)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# load_model
# ---------------------------------------------------------------------------


def test_load_model_file_not_found():
    with pytest.raises(FileNotFoundError, match="Model artifact not found"):
        load_model(Path("/nonexistent/model.json"))


def test_load_model_success(tmp_path):
    from xgboost import XGBRegressor

    model = XGBRegressor(n_estimators=10, random_state=42)
    X = np.random.rand(20, 3)
    y = np.random.rand(20)
    model.fit(X, y)
    path = tmp_path / "model.json"
    model.save_model(str(path))

    loaded = load_model(path)
    assert loaded is not None
    preds = loaded.predict(X)
    assert len(preds) == 20


# ---------------------------------------------------------------------------
# load_features
# ---------------------------------------------------------------------------


def test_load_features_empty():
    engine = MagicMock()
    with patch("pipeline.ml.predict.pd.read_sql", return_value=pd.DataFrame()):
        with pytest.raises(ValueError, match="No features found"):
            load_features(engine, race_id=999)


def test_load_features_success():
    fd1 = _make_feature_data()
    fd2 = _make_feature_data()
    features_db_df = pd.DataFrame(
        {
            "driver_id": [1, 2],
            "feature_data": [fd1, fd2],
        }
    )
    qualifying_db_df = pd.DataFrame(
        {
            "driver_id": [1, 2],
            "constructor_id": [10, 20],
        }
    )
    engine = MagicMock()
    with patch(
        "pipeline.ml.predict.pd.read_sql",
        side_effect=[features_db_df, qualifying_db_df],
    ):
        result = load_features(engine, race_id=1)

    assert len(result) == 2
    assert "driver_id" in result.columns
    assert "constructor_id" in result.columns
    for col in FEATURE_COLS:
        assert col in result.columns, f"Missing feature column: {col}"


def test_load_features_warns_on_missing_qualifying(caplog):
    """load_features logs a warning when a driver has features but no qualifying result."""
    import logging

    fd1 = _make_feature_data()
    fd2 = _make_feature_data()
    features_db_df = pd.DataFrame(
        {
            "driver_id": [1, 2],
            "feature_data": [fd1, fd2],
        }
    )
    # Only driver 1 has a qualifying result; driver 2 will be dropped.
    qualifying_db_df = pd.DataFrame(
        {
            "driver_id": [1],
            "constructor_id": [10],
        }
    )
    engine = MagicMock()
    with patch(
        "pipeline.ml.predict.pd.read_sql",
        side_effect=[features_db_df, qualifying_db_df],
    ):
        with caplog.at_level(logging.WARNING, logger="pipeline.ml.predict"):
            result = load_features(engine, race_id=1)

    assert len(result) == 1
    assert any("dropped" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# prepare_features
# ---------------------------------------------------------------------------


def test_prepare_features():
    df = _make_features_df(3)
    result = prepare_features(df)
    assert result["circuit_type"].dtype.name == "category"
    assert result["is_wet_race_forecast"].dtype in (np.int64, np.int32, int)


# ---------------------------------------------------------------------------
# normalise_positions
# ---------------------------------------------------------------------------


def test_normalise_positions_basic():
    raw = np.array([3.5, 1.2, 7.0, 2.8])
    positions = normalise_positions(raw)
    assert positions == [3, 1, 4, 2]


def test_normalise_positions_range():
    raw = np.array([10.0, 5.0, 15.0, 1.0, 8.0])
    positions = normalise_positions(raw)
    assert sorted(positions) == [1, 2, 3, 4, 5]
    assert len(set(positions)) == 5  # no ties


def test_normalise_positions_single():
    raw = np.array([42.0])
    positions = normalise_positions(raw)
    assert positions == [1]


def test_normalise_positions_close_values():
    """Close predictions should still produce unique positions."""
    raw = np.array([5.001, 5.002, 5.003])
    positions = normalise_positions(raw)
    assert sorted(positions) == [1, 2, 3]


def test_normalise_positions_stability():
    """Identical inputs produce identical positions across repeated calls."""
    raw = np.array([5.0, 5.0, 3.0])
    assert normalise_positions(raw) == normalise_positions(raw)
    # The element with the lowest value (3.0, index 2) should always be position 1.
    assert normalise_positions(raw)[2] == 1


# ---------------------------------------------------------------------------
# store_predictions
# ---------------------------------------------------------------------------


def test_store_predictions():
    predictions = pd.DataFrame(
        {
            "driver_id": [1, 2, 3],
            "constructor_id": [10, 20, 30],
            "predicted_position": [1, 2, 3],
        }
    )
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    count = store_predictions(mock_engine, race_id=1, model_version_id=1, predictions=predictions)
    assert count == 3
    mock_conn.execute.assert_called_once()


# ---------------------------------------------------------------------------
# run (end-to-end with mocks)
# ---------------------------------------------------------------------------


def test_run_end_to_end(tmp_path):
    """Test the full prediction pipeline with a real model and mocked DB."""
    from xgboost import XGBRegressor

    # Train a small model with the right number of features
    n_features = len(FEATURE_COLS)
    X = np.random.RandomState(42).rand(40, n_features)
    y = np.random.RandomState(42).randint(1, 21, size=40).astype(float)
    model = XGBRegressor(n_estimators=10, random_state=42, enable_categorical=False)
    model.fit(X, y)
    model_path = tmp_path / "model.json"
    model.save_model(str(model_path))

    # Create mock feature data for 5 drivers
    features_df = _make_features_df(5)

    # Mock the engine
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with patch("pipeline.ml.predict.load_features", return_value=features_df):
        result = run(
            race_id=1,
            model_version_id=1,
            model_path=model_path,
            engine=mock_engine,
        )

    assert len(result) == 5
    assert set(result.columns) == {"driver_id", "constructor_id", "predicted_position"}
    positions = sorted(result["predicted_position"].tolist())
    assert positions == [1, 2, 3, 4, 5]  # unique 1..N


def test_run_raises_on_missing_feature_columns(tmp_path):
    """run() raises ValueError when loaded features are missing expected columns."""
    from xgboost import XGBRegressor

    n_features = len(FEATURE_COLS)
    X = np.random.RandomState(42).rand(40, n_features)
    y = np.random.RandomState(42).randint(1, 21, size=40).astype(float)
    model = XGBRegressor(n_estimators=10, random_state=42, enable_categorical=False)
    model.fit(X, y)
    model_path = tmp_path / "model.json"
    model.save_model(str(model_path))

    # Drop one required column to trigger the guard.
    incomplete_df = _make_features_df(3).drop(columns=["grid_position"])

    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with patch("pipeline.ml.predict.load_features", return_value=incomplete_df):
        with pytest.raises(ValueError, match="Feature columns missing from loaded data"):
            run(
                race_id=1,
                model_version_id=1,
                model_path=model_path,
                engine=mock_engine,
            )
