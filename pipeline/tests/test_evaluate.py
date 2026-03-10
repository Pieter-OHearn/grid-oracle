"""Unit tests for pipeline.ml.evaluate."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from pipeline.ml.evaluate import (
    compute_metrics,
    load_comparison,
    run,
    store_metrics,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_comparison_df(
    predicted: list[int],
    actual: list[int | None],
    statuses: list[str] | None = None,
) -> pd.DataFrame:
    """Build a prediction-vs-result DataFrame for testing."""
    n = len(predicted)
    if statuses is None:
        statuses = ["Finished"] * n
    return pd.DataFrame(
        {
            "driver_id": list(range(1, n + 1)),
            "predicted_position": predicted,
            "finish_position": [float(a) if a is not None else None for a in actual],
            "status": statuses,
        }
    )


# ---------------------------------------------------------------------------
# load_comparison
# ---------------------------------------------------------------------------


def test_load_comparison_empty():
    engine = MagicMock()
    with patch("pipeline.ml.evaluate.pd.read_sql", return_value=pd.DataFrame()):
        with pytest.raises(ValueError, match="No prediction/result pairs"):
            load_comparison(engine, race_id=1, model_version_id=1)


def test_load_comparison_success():
    df = _make_comparison_df([1, 2, 3], [1, 3, 2])
    engine = MagicMock()
    with patch("pipeline.ml.evaluate.pd.read_sql", return_value=df):
        result = load_comparison(engine, race_id=1, model_version_id=1)

    assert len(result) == 3
    assert "predicted_position" in result.columns
    assert "finish_position" in result.columns


# ---------------------------------------------------------------------------
# compute_metrics
# ---------------------------------------------------------------------------


def test_compute_metrics_perfect_predictions():
    df = _make_comparison_df([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    metrics = compute_metrics(df)

    assert metrics["exact_position_accuracy"] == 1.0
    assert metrics["top3_accuracy"] == 1.0
    assert metrics["mean_position_error"] == 0.0


def test_compute_metrics_mostly_wrong():
    df = _make_comparison_df([5, 4, 3, 2, 1], [1, 2, 3, 4, 5])
    metrics = compute_metrics(df)

    # Position 3 predicted as 3 is exact — only the middle driver matches
    assert metrics["exact_position_accuracy"] == pytest.approx(1 / 5)
    # Top-3 actual finishers (pos 1,2,3) were predicted as 5,4,3 — only driver at pos 3 is correct
    assert metrics["top3_accuracy"] == pytest.approx(1 / 3, abs=1e-4)
    # Errors: |5-1|+|4-2|+|3-3|+|2-4|+|1-5| = 4+2+0+2+4 = 12, mean = 2.4
    assert metrics["mean_position_error"] == pytest.approx(2.4, abs=1e-4)


def test_compute_metrics_with_dnf():
    """DNF drivers (finish_position=None) are excluded from metrics."""
    df = _make_comparison_df(
        [1, 2, 3, 4, 5],
        [1, 2, None, 4, None],
        ["Finished", "Finished", "Retired", "Finished", "DNF"],
    )
    metrics = compute_metrics(df)

    # 3 classified finishers: (1,1), (2,2), (4,4) — all exact matches
    assert metrics["exact_position_accuracy"] == 1.0
    # Actual top-3 finishers among classified: positions 1 and 2
    # Both predicted correctly in top 3
    assert metrics["top3_accuracy"] == 1.0
    assert metrics["mean_position_error"] == 0.0


def test_compute_metrics_all_dnf():
    """All drivers DNF — metrics should be zero."""
    df = _make_comparison_df(
        [1, 2, 3],
        [None, None, None],
        ["Retired", "DNF", "Collision"],
    )
    metrics = compute_metrics(df)

    assert metrics["exact_position_accuracy"] == 0.0
    assert metrics["top3_accuracy"] == 0.0
    assert metrics["mean_position_error"] == 0.0


def test_compute_metrics_partial_top3():
    """Some top-3 finishers predicted outside top 3."""
    df = _make_comparison_df(
        [1, 4, 2, 3, 5],
        [1, 2, 3, 4, 5],
    )
    metrics = compute_metrics(df)

    # Actual top 3: drivers finishing 1,2,3
    # Driver finishing 1st was predicted 1st (correct)
    # Driver finishing 2nd was predicted 4th (wrong)
    # Driver finishing 3rd was predicted 2nd (correct)
    assert metrics["top3_accuracy"] == pytest.approx(2 / 3, abs=1e-4)


# ---------------------------------------------------------------------------
# store_metrics
# ---------------------------------------------------------------------------


def test_store_metrics():
    metrics = {
        "exact_position_accuracy": 0.4,
        "top3_accuracy": 0.6667,
        "mean_position_error": 2.35,
    }
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    store_metrics(mock_engine, race_id=1, model_version_id=1, metrics=metrics)

    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args
    row = call_args[0][1]
    assert row["exact_position_accuracy"] == 0.4
    assert row["top3_accuracy"] == 0.6667
    assert row["mean_position_error"] == 2.35


# ---------------------------------------------------------------------------
# run (end-to-end with mocks)
# ---------------------------------------------------------------------------


def test_run_end_to_end(capsys):
    """Full evaluation pipeline with mocked DB."""
    comparison_df = _make_comparison_df([1, 2, 3, 4, 5], [1, 3, 2, 4, 5])

    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with patch("pipeline.ml.evaluate.load_comparison", return_value=comparison_df):
        metrics = run(race_id=1, model_version_id=1, engine=mock_engine)

    # 3 exact matches out of 5: positions 1, 4, 5
    assert metrics["exact_position_accuracy"] == pytest.approx(3 / 5)
    # Mean error: |0|+|1|+|1|+|0|+|0| = 2, mean = 0.4
    assert metrics["mean_position_error"] == pytest.approx(0.4)

    # Verify human-readable summary was printed
    captured = capsys.readouterr()
    assert "Exact position" in captured.out
    assert "Top-3 accuracy" in captured.out
    assert "Mean position err" in captured.out

    # Verify metrics were stored
    mock_conn.execute.assert_called_once()
