"""Unit tests for pipeline.ml.train."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from pipeline.ml.train import (
    attach_targets,
    insert_model_version,
    load_feature_parquets,
    prepare_features,
    save_model,
    train_model,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature_df(n: int = 20, season: int = 2023) -> pd.DataFrame:
    """Create a synthetic feature DataFrame with target and season columns."""
    rng = np.random.RandomState(42)
    rows = []
    race_id = season * 100
    for i in range(n):
        rows.append(
            {
                "race_id": race_id + i // 20,
                "driver_id": i + 1,
                "grid_position": rng.randint(1, 21),
                "driver_avg_position_last_3_races": rng.uniform(1, 20),
                "driver_avg_position_at_circuit": rng.uniform(1, 20),
                "driver_podium_rate_at_circuit": rng.uniform(0, 1),
                "constructor_avg_position_last_3_races": rng.uniform(1, 20),
                "constructor_avg_position_at_circuit": rng.uniform(1, 20),
                "circuit_type": rng.choice(["street", "road", "high-speed"]),
                "is_wet_race_forecast": rng.choice([True, False]),
                "driver_wet_race_avg_position": rng.uniform(1, 20),
                "constructor_wet_race_avg_position": rng.uniform(1, 20),
                "driver_season_avg_position": rng.uniform(1, 20),
                "championship_position": rng.randint(1, 21),
                "finish_position": rng.randint(1, 21),
                "season": season,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# load_feature_parquets
# ---------------------------------------------------------------------------


def test_load_feature_parquets(tmp_path):
    df1 = pd.DataFrame({"race_id": [1], "driver_id": [1], "grid_position": [3]})
    df2 = pd.DataFrame({"race_id": [2], "driver_id": [2], "grid_position": [5]})
    df1.to_parquet(tmp_path / "features_1.parquet", index=False)
    df2.to_parquet(tmp_path / "features_2.parquet", index=False)

    result = load_feature_parquets(tmp_path)
    assert len(result) == 2
    assert set(result["race_id"]) == {1, 2}


def test_load_feature_parquets_no_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_feature_parquets(tmp_path)


# ---------------------------------------------------------------------------
# attach_targets
# ---------------------------------------------------------------------------


def test_attach_targets():
    features_df = pd.DataFrame({"race_id": [1, 1, 2], "driver_id": [10, 20, 10], "grid_position": [1, 2, 3]})
    db_results = pd.DataFrame(
        {
            "race_id": [1, 1],
            "driver_id": [10, 20],
            "finish_position": [1, 3],
            "season": [2023, 2023],
        }
    )
    engine = MagicMock()
    with patch("pipeline.ml.train.pd.read_sql", return_value=db_results):
        result = attach_targets(features_df, engine)

    assert len(result) == 2  # race_id=2 dropped (no result)
    assert "finish_position" in result.columns
    assert "season" in result.columns


# ---------------------------------------------------------------------------
# prepare_features
# ---------------------------------------------------------------------------


def test_prepare_features():
    df = pd.DataFrame(
        {
            "circuit_type": ["street", "road", "street"],
            "is_wet_race_forecast": [True, False, True],
        }
    )
    result = prepare_features(df)
    assert result["circuit_type"].dtype.name == "category"
    assert result["is_wet_race_forecast"].dtype in (np.int64, np.int32, int)
    assert list(result["is_wet_race_forecast"]) == [1, 0, 1]


# ---------------------------------------------------------------------------
# train_model
# ---------------------------------------------------------------------------


def test_train_model():
    train_df = _make_feature_df(n=40, season=2023)
    test_df = _make_feature_df(n=20, season=2024)
    df = pd.concat([train_df, test_df], ignore_index=True)

    model, mae, race_count = train_model(df, train_seasons=[2023], test_seasons=[2024])

    assert model is not None
    assert mae >= 0
    assert race_count == 2


def test_train_model_no_train_data():
    df = _make_feature_df(n=20, season=2024)
    with pytest.raises(ValueError, match="No training data"):
        train_model(df, train_seasons=[2023], test_seasons=[2024])


def test_train_model_no_test_data():
    df = _make_feature_df(n=20, season=2023)
    with pytest.raises(ValueError, match="No test data"):
        train_model(df, train_seasons=[2023], test_seasons=[2024])


# ---------------------------------------------------------------------------
# save_model
# ---------------------------------------------------------------------------


def test_save_model(tmp_path):
    df = _make_feature_df(n=40, season=2023)
    test_df = _make_feature_df(n=20, season=2024)
    combined = pd.concat([df, test_df], ignore_index=True)

    model, _, _ = train_model(combined, train_seasons=[2023], test_seasons=[2024])

    out = tmp_path / "model.json"
    save_model(model, out)
    assert out.exists()
    assert out.stat().st_size > 0


# ---------------------------------------------------------------------------
# insert_model_version
# ---------------------------------------------------------------------------


def test_insert_model_version():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (42,)
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    result = insert_model_version(
        mock_engine,
        name="xgb_v1",
        training_races_count=10,
        mae=1.5,
        train_seasons=[2022, 2023],
        test_seasons=[2024],
    )
    assert result == 42
    mock_conn.execute.assert_called_once()


def test_insert_model_version_no_row():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(RuntimeError, match="returned no row"):
        insert_model_version(
            mock_engine,
            name="xgb_v1",
            training_races_count=10,
            mae=1.5,
            train_seasons=[2022],
            test_seasons=[2024],
        )
