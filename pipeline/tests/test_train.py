"""Unit tests for pipeline.ml.train."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from pipeline.ml.features import prepare_features
from pipeline.ml.train import (
    attach_targets,
    insert_model_version,
    load_feature_parquets,
    save_model,
    train_model,
    update_artifact_path,
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
    assert result["circuit_type"].dtype == float
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
        triggered_by_race_id=7,
    )
    assert result == 42
    mock_conn.execute.assert_called_once()
    call_params = mock_conn.execute.call_args[0][1]
    assert call_params["train_seasons"] == [2022, 2023]
    assert call_params["test_season"] == 2024
    assert call_params["triggered_by_race_id"] == 7


def test_insert_model_version_no_triggered_race():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (1,)
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    result = insert_model_version(
        mock_engine,
        name="xgb_v1",
        training_races_count=5,
        mae=2.0,
        train_seasons=[2022],
        test_seasons=[2023],
    )
    assert result == 1
    call_params = mock_conn.execute.call_args[0][1]
    assert call_params["triggered_by_race_id"] is None


def test_update_artifact_path():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.rowcount = 1
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    update_artifact_path(mock_engine, model_version_id=7, artifact_path=Path("/some/model_v7.json"))
    mock_conn.execute.assert_called_once()


def test_update_artifact_path_no_row():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.rowcount = 0
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(RuntimeError, match="no model_versions row found"):
        update_artifact_path(mock_engine, model_version_id=99, artifact_path=Path("/some/model_v99.json"))


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


# ---------------------------------------------------------------------------
# run — artifact path auto-derivation
# ---------------------------------------------------------------------------


def test_run_derives_artifact_path_when_none(tmp_path):
    """When artifact_path=None, run() saves to model_v{id}.json and records it in the DB."""
    from pipeline.ml.train import run

    train_df = _make_feature_df(n=40, season=2023)
    test_df = _make_feature_df(n=20, season=2024)
    combined_df = pd.concat([train_df, test_df], ignore_index=True)

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (99,)
    mock_conn.execute.return_value.rowcount = 1
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch("pipeline.ml.train.get_engine", return_value=mock_engine),
        patch("pipeline.ml.train.load_feature_parquets", return_value=combined_df),
        patch("pipeline.ml.train.attach_targets", return_value=combined_df),
        patch("pipeline.ml.train.ARTIFACTS_DIR", tmp_path),
    ):
        model_version_id = run(
            data_dir=tmp_path,
            artifact_path=None,
            engine=mock_engine,
            train_seasons=[2023],
            test_seasons=[2024],
        )

    assert model_version_id == 99
    expected_path = tmp_path / "model_v99.json"
    assert expected_path.exists()
    # insert_model_version + update_artifact_path = 2 DB calls
    assert mock_conn.execute.call_count == 2


def test_run_explicit_artifact_path(tmp_path):
    """When artifact_path is provided explicitly, run() saves to that path and records it in DB."""
    from pipeline.ml.train import run

    train_df = _make_feature_df(n=40, season=2023)
    test_df = _make_feature_df(n=20, season=2024)
    combined_df = pd.concat([train_df, test_df], ignore_index=True)

    explicit_path = tmp_path / "my_model.json"

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (5,)
    mock_conn.execute.return_value.rowcount = 1
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch("pipeline.ml.train.load_feature_parquets", return_value=combined_df),
        patch("pipeline.ml.train.attach_targets", return_value=combined_df),
    ):
        run(
            data_dir=tmp_path,
            artifact_path=explicit_path,
            engine=mock_engine,
            train_seasons=[2023],
            test_seasons=[2024],
        )

    assert explicit_path.exists()
    # insert_model_version + update_artifact_path = 2 DB calls
    assert mock_conn.execute.call_count == 2


def test_run_rolls_back_db_row_if_save_model_fails(tmp_path):
    """If save_model raises, run() deletes the orphaned model_versions row and re-raises."""
    from pipeline.ml.train import run

    train_df = _make_feature_df(n=40, season=2023)
    test_df = _make_feature_df(n=20, season=2024)
    combined_df = pd.concat([train_df, test_df], ignore_index=True)

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (7,)
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch("pipeline.ml.train.load_feature_parquets", return_value=combined_df),
        patch("pipeline.ml.train.attach_targets", return_value=combined_df),
        patch("pipeline.ml.train.save_model", side_effect=OSError("disk full")),
    ):
        with pytest.raises(OSError, match="disk full"):
            run(
                data_dir=tmp_path,
                artifact_path=tmp_path / "model.json",
                engine=mock_engine,
                train_seasons=[2023],
                test_seasons=[2024],
            )

    # insert_model_version + _delete_model_version = 2 DB calls (no update_artifact_path)
    assert mock_conn.execute.call_count == 2
