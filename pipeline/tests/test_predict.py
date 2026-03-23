"""Unit tests for pipeline.ml.predict."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from pipeline.ml.features import prepare_features
from pipeline.ml.predict import (
    compute_confidence_scores,
    load_features,
    load_model,
    normalise_positions,
    resolve_artifact_path,
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
        "driver_championship_position": int(rng.randint(1, 21)),
        "constructor_championship_position": int(rng.randint(1, 11)),
        "constructor_dnf_rate_last_season": float(rng.uniform(0, 1)),
        "driver_avg_sector2_time_at_circuit": float(rng.uniform(1.0, 1.3)),
        "constructor_avg_fp2_pace_at_circuit": float(rng.uniform(1.0, 1.3)),
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
# resolve_artifact_path
# ---------------------------------------------------------------------------


def test_resolve_artifact_path_success():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = ("/artifacts/model_v3.json",)
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    result = resolve_artifact_path(mock_engine, model_version_id=3)
    assert result == Path("/artifacts/model_v3.json")


def test_resolve_artifact_path_no_row():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(ValueError, match="No artifact_path recorded"):
        resolve_artifact_path(mock_engine, model_version_id=99)


def test_resolve_artifact_path_null_column():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (None,)
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(ValueError, match="No artifact_path recorded"):
        resolve_artifact_path(mock_engine, model_version_id=5)


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
    assert result["circuit_type"].dtype == float
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
# compute_confidence_scores
# ---------------------------------------------------------------------------


def test_compute_confidence_scores_single():
    assert compute_confidence_scores(np.array([5.0])) == [1.0]


def test_compute_confidence_scores_range():
    """All scores should be in [0, 1] and the max gap driver should score 1.0."""
    raw = np.array([1.0, 2.0, 10.0, 10.5, 11.0])
    scores = compute_confidence_scores(raw)
    assert len(scores) == 5
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert max(scores) == pytest.approx(1.0)


def test_compute_confidence_scores_winner_not_last():
    """The predicted winner (lowest raw score) should have higher confidence
    than bunched midfield drivers when clearly separated."""
    # Driver 0 has a very separated predicted P1; drivers 1-4 are tightly bunched
    raw = np.array([1.0, 5.0, 5.1, 5.2, 5.3])
    scores = compute_confidence_scores(raw)
    # Driver 0 (P1) has gap=4.0 to its only neighbour → normalised to 1.0
    assert scores[0] == pytest.approx(1.0)
    # Bunched midfield takes the min gap (0.1) → much lower confidence
    assert scores[1] < scores[0]
    assert scores[2] < scores[0]


def test_compute_confidence_scores_identical():
    """Identical raw scores should all return 1.0 (not divide-by-zero)."""
    raw = np.array([3.0, 3.0, 3.0])
    scores = compute_confidence_scores(raw)
    assert scores == pytest.approx([1.0, 1.0, 1.0])


def test_compute_confidence_scores_preserves_original_order():
    """Scores are returned in the original driver order, not sorted order."""
    raw = np.array([10.0, 1.0, 5.0])
    scores = compute_confidence_scores(raw)
    # Driver at index 1 has raw=1.0 (predicted P1) — large gap ahead
    assert len(scores) == 3
    # Re-check that aligning back to original order is correct by symmetry
    # Sorted: 1.0 (idx 1), 5.0 (idx 2), 10.0 (idx 0)
    # gaps:    4.0,          min(4,5)=4,   5.0  → max_gap=5
    # normalised: 0.8,       0.8,          1.0
    assert scores[0] == pytest.approx(1.0)  # raw 10.0 → last, gap=5 → 1.0
    assert scores[1] == pytest.approx(0.8)  # raw 1.0 → P1, gap=4 → 0.8
    assert scores[2] == pytest.approx(0.8)  # raw 5.0 → P2, gap=min(4,5)=4 → 0.8


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

    count = store_predictions(
        mock_engine,
        race_id=1,
        model_version_id=1,
        predictions=predictions,
        confidence_scores=[0.9, 0.5, 0.3],
    )
    assert count == 3
    mock_conn.execute.assert_called_once()


def test_store_predictions_no_confidence():
    """store_predictions still works when confidence_scores is omitted (stores NULL)."""
    predictions = pd.DataFrame(
        {
            "driver_id": [1, 2],
            "constructor_id": [10, 20],
            "predicted_position": [1, 2],
        }
    )
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    count = store_predictions(mock_engine, race_id=1, model_version_id=1, predictions=predictions)
    assert count == 2


def test_store_predictions_short_confidence_raises():
    """store_predictions raises ValueError when confidence_scores is shorter than predictions."""
    predictions = pd.DataFrame(
        {
            "driver_id": [1, 2, 3],
            "constructor_id": [10, 20, 30],
            "predicted_position": [1, 2, 3],
        }
    )
    mock_engine = MagicMock()
    with pytest.raises(ValueError, match="confidence_scores length"):
        store_predictions(
            mock_engine,
            race_id=1,
            model_version_id=1,
            predictions=predictions,
            confidence_scores=[0.9, 0.5],  # one element short
        )


def test_store_predictions_long_confidence_raises():
    """store_predictions raises ValueError when confidence_scores is longer than predictions."""
    predictions = pd.DataFrame(
        {
            "driver_id": [1, 2],
            "constructor_id": [10, 20],
            "predicted_position": [1, 2],
        }
    )
    mock_engine = MagicMock()
    with pytest.raises(ValueError, match="confidence_scores length"):
        store_predictions(
            mock_engine,
            race_id=1,
            model_version_id=1,
            predictions=predictions,
            confidence_scores=[0.9, 0.5, 0.3],  # one element too many
        )


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


def test_run_resolves_path_from_db_when_none(tmp_path):
    """run() loads the model from the DB-stored artifact_path when model_path is None."""
    from xgboost import XGBRegressor

    n_features = len(FEATURE_COLS)
    X = np.random.RandomState(0).rand(40, n_features)
    y = np.random.RandomState(0).randint(1, 21, size=40).astype(float)
    model = XGBRegressor(n_estimators=10, random_state=42, enable_categorical=False)
    model.fit(X, y)
    model_path = tmp_path / "model_v7.json"
    model.save_model(str(model_path))

    features_df = _make_features_df(5)

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (str(model_path),)
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with patch("pipeline.ml.predict.load_features", return_value=features_df):
        result = run(
            race_id=1,
            model_version_id=7,
            model_path=None,
            engine=mock_engine,
        )

    assert len(result) == 5
    assert sorted(result["predicted_position"].tolist()) == [1, 2, 3, 4, 5]


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
