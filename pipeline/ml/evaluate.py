"""Post-race evaluation — compare predictions to actual results."""

import argparse
import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.ingest.upsert_helpers import get_engine

logger = logging.getLogger(__name__)


def load_comparison(engine: Engine, race_id: int, model_version_id: int) -> pd.DataFrame:
    """Load predictions alongside actual race results for a given race.

    Returns a DataFrame with columns:
        driver_id, predicted_position, finish_position, status

    Drivers who did not finish (DNF) have ``finish_position`` set to NULL in
    the database.  They are included in the returned DataFrame so callers can
    decide how to handle them.
    """
    query = text(
        """
        SELECT p.driver_id,
               p.predicted_position,
               rr.finish_position,
               rr.status
        FROM predictions p
        JOIN race_results rr
          ON rr.race_id = p.race_id
         AND rr.driver_id = p.driver_id
        JOIN races r
          ON r.id = p.race_id
        WHERE r.is_completed = TRUE
          AND p.race_id = :race_id
          AND p.model_version_id = :model_version_id
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"race_id": race_id, "model_version_id": model_version_id})

    if df.empty:
        raise ValueError(f"No prediction/result pairs found for race_id={race_id}, model_version_id={model_version_id}")

    logger.info(
        "Loaded %d prediction/result pairs for race_id=%d, model_version_id=%d",
        len(df),
        race_id,
        model_version_id,
    )
    return df


def compute_metrics(df: pd.DataFrame) -> dict[str, float]:
    """Compute evaluation metrics from a prediction-vs-result DataFrame.

    DNF drivers (``finish_position`` is NULL) are excluded from position-based
    accuracy metrics.

    Returns a dict with keys:
        exact_position_accuracy, top3_accuracy, mean_position_error
    """
    classified = df.dropna(subset=["finish_position"]).copy()

    if classified.empty:
        logger.warning("No classified finishers — all drivers DNF'd; metrics will be zero.")
        return {
            "exact_position_accuracy": 0.0,
            "top3_accuracy": 0.0,
            "mean_position_error": 0.0,
        }

    n = len(classified)

    # Exact position accuracy: % of drivers predicted in exact position
    exact_matches = (classified["predicted_position"] == classified["finish_position"]).sum()
    exact_position_accuracy = exact_matches / n

    # Top-3 accuracy: % of actual top-3 finishers that were predicted top 3
    actual_top3 = classified[classified["finish_position"] <= 3]
    if len(actual_top3) == 0:
        top3_accuracy = 0.0
    else:
        correct_top3 = (actual_top3["predicted_position"] <= 3).sum()
        top3_accuracy = correct_top3 / len(actual_top3)

    # Mean position error: average |predicted - actual|
    errors = (classified["predicted_position"] - classified["finish_position"]).abs()
    mean_position_error = errors.mean()

    return {
        "exact_position_accuracy": round(float(exact_position_accuracy), 4),
        "top3_accuracy": round(float(top3_accuracy), 4),
        "mean_position_error": round(float(mean_position_error), 4),
    }


def store_metrics(
    engine: Engine,
    race_id: int,
    model_version_id: int,
    metrics: dict[str, float],
) -> None:
    """Insert evaluation metrics into the evaluation_metrics table.

    Uses ON CONFLICT to allow re-running without duplicates.
    """
    row = {
        "race_id": race_id,
        "model_version_id": model_version_id,
        "evaluated_at": datetime.now(timezone.utc),
        "exact_position_accuracy": metrics["exact_position_accuracy"],
        "top3_accuracy": metrics["top3_accuracy"],
        "mean_position_error": metrics["mean_position_error"],
    }

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO evaluation_metrics
                    (race_id, model_version_id, evaluated_at,
                     exact_position_accuracy, top3_accuracy, mean_position_error)
                VALUES
                    (:race_id, :model_version_id, :evaluated_at,
                     :exact_position_accuracy, :top3_accuracy, :mean_position_error)
                ON CONFLICT (race_id, model_version_id) DO UPDATE
                    SET evaluated_at             = EXCLUDED.evaluated_at,
                        exact_position_accuracy  = EXCLUDED.exact_position_accuracy,
                        top3_accuracy            = EXCLUDED.top3_accuracy,
                        mean_position_error      = EXCLUDED.mean_position_error
                """
            ),
            row,
        )

    logger.info(
        "Stored evaluation metrics for race_id=%d, model_version_id=%d",
        race_id,
        model_version_id,
    )


def log_summary(
    race_id: int,
    model_version_id: int,
    metrics: dict[str, float],
    total_drivers: int,
    classified_drivers: int,
) -> None:
    """Print a human-readable evaluation summary to the console."""
    dnf_count = total_drivers - classified_drivers
    print(
        f"\n{'=' * 50}\n"
        f"  Evaluation — race {race_id}, model {model_version_id}\n"
        f"{'=' * 50}\n"
        f"  Drivers evaluated : {classified_drivers} / {total_drivers}"
        f" ({dnf_count} DNF excluded)\n"
        f"  Exact position    : {metrics['exact_position_accuracy']:.1%}\n"
        f"  Top-3 accuracy    : {metrics['top3_accuracy']:.1%}\n"
        f"  Mean position err : {metrics['mean_position_error']:.2f}\n"
        f"{'=' * 50}\n"
    )


def run(
    race_id: int,
    model_version_id: int,
    engine: Engine | None = None,
) -> dict[str, float]:
    """End-to-end evaluation pipeline for a single race.

    Returns the computed metrics dict.
    """
    if engine is None:
        engine = get_engine()

    df = load_comparison(engine, race_id, model_version_id)

    metrics = compute_metrics(df)
    store_metrics(engine, race_id, model_version_id, metrics)

    classified = df.dropna(subset=["finish_position"])
    log_summary(race_id, model_version_id, metrics, len(df), len(classified))

    return metrics


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Evaluate predictions against actual race results.")
    parser.add_argument(
        "--race-id",
        type=int,
        required=True,
        help="ID of the completed race to evaluate",
    )
    parser.add_argument(
        "--model-version-id",
        type=int,
        required=True,
        help="ID of the model version whose predictions to evaluate",
    )
    args = parser.parse_args()

    run(race_id=args.race_id, model_version_id=args.model_version_id)


if __name__ == "__main__":
    main()
