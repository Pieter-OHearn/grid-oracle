"""Unit tests for pipeline.ml.workflow."""

from unittest.mock import MagicMock, patch

import pandas as pd

from pipeline.ml.context import PREWEEKEND_CONTEXT
from pipeline.ml.workflow import post_race_pipeline, walk_forward_backtest


@patch(
    "pipeline.ml.workflow._get_completed_races",
    return_value=[
        {"race_id": 11, "season": 2022, "round": 1, "date": "2022-03-20"},
        {"race_id": 12, "season": 2022, "round": 2, "date": "2022-03-27"},
        {"race_id": 21, "season": 2023, "round": 1, "date": "2023-03-05"},
    ],
)
@patch("pipeline.ml.workflow.post_race_pipeline", side_effect=[102, 103])
@patch("pipeline.ml.workflow.ml_predict.run")
@patch("pipeline.ml.workflow.retrain_model", return_value=101)
def test_walk_forward_backtest_replays_races_in_order(
    mock_retrain,
    mock_predict,
    mock_post_race,
    mock_completed,
):
    engine = MagicMock()

    result = walk_forward_backtest(engine)

    assert result == 103
    mock_retrain.assert_called_once_with(11, engine)
    mock_predict.assert_any_call(race_id=12, model_version_id=101, engine=engine)
    mock_predict.assert_any_call(race_id=21, model_version_id=102, engine=engine)
    mock_post_race.assert_any_call(12, 2022, engine, refresh_future_predictions=False)
    mock_post_race.assert_any_call(21, 2023, engine, refresh_future_predictions=False)


@patch("pipeline.ml.workflow.predict_remaining_races")
@patch("pipeline.ml.workflow.ml_train.run", return_value=42)
@patch("pipeline.ml.workflow._get_cumulative_backtest_mae", return_value=1.75)
@patch("pipeline.ml.workflow.export_parquet")
@patch("pipeline.ml.workflow.build_features_for_race")
@patch("pipeline.ml.workflow.evaluate_race")
def test_post_race_pipeline_retrains_from_preweekend_snapshots(
    mock_evaluate,
    mock_build,
    mock_export,
    mock_backtest_mae,
    mock_train,
    mock_predict_remaining,
):
    mock_build.return_value = pd.DataFrame({"driver_id": [1]})
    engine = MagicMock()

    result = post_race_pipeline(10, 2026, engine)

    assert result == 42
    mock_evaluate.assert_called_once_with(10, engine)
    mock_build.assert_called_once_with(10, engine, context=PREWEEKEND_CONTEXT)
    mock_export.assert_called_once_with(mock_build.return_value, 10, context=PREWEEKEND_CONTEXT)
    mock_backtest_mae.assert_called_once_with(10, engine)
    mock_train.assert_called_once_with(
        engine=engine,
        triggered_by_race_id=10,
        through_race_id=10,
        evaluation_mae=1.75,
    )
    mock_predict_remaining.assert_called_once_with(2026, 42, engine)
