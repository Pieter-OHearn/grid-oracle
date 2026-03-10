"""Generate pre-race predictions using a trained XGBoost model."""

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from xgboost import XGBRegressor

from pipeline.ingest.upsert_helpers import get_engine
from pipeline.ml.features import ARTIFACTS_DIR, prepare_features
from pipeline.ml.train import FEATURE_COLS

logger = logging.getLogger(__name__)


def load_model(path: Path) -> XGBRegressor:
    """Load a trained XGBRegressor from a JSON artifact."""
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}")
    model = XGBRegressor()
    model.load_model(str(path))
    logger.info("Loaded model from %s", path)
    return model


def load_features(engine: Engine, race_id: int) -> pd.DataFrame:
    """Load feature rows from the features table for a given race.

    Fetches features and qualifying results separately, then merges them in
    Python so that any drivers missing from qualifying_results are detected
    and logged rather than silently dropped.

    Returns a DataFrame with one row per driver, containing the
    feature columns expected by the model.
    """
    with engine.connect() as conn:
        features_raw = pd.read_sql(
            text("SELECT driver_id, feature_data FROM features WHERE race_id = :race_id"),
            conn,
            params={"race_id": race_id},
        )
        qualifying_raw = pd.read_sql(
            text("SELECT driver_id, constructor_id FROM qualifying_results WHERE race_id = :race_id"),
            conn,
            params={"race_id": race_id},
        )

    if features_raw.empty:
        raise ValueError(f"No features found for race_id={race_id}")

    # Expand the JSONB feature_data column into separate columns.
    feature_records = pd.json_normalize(features_raw["feature_data"])
    expanded = pd.concat(
        [features_raw[["driver_id"]].reset_index(drop=True), feature_records],
        axis=1,
    )

    result = expanded.merge(qualifying_raw, on="driver_id", how="inner")

    dropped = len(expanded) - len(result)
    if dropped > 0:
        logger.warning(
            "%d driver(s) dropped for race_id=%d: present in features but missing from qualifying_results",
            dropped,
            race_id,
        )

    logger.info("Loaded features for %d drivers (race_id=%d)", len(result), race_id)
    return result


def normalise_positions(raw_predictions: np.ndarray) -> list[int]:
    """Convert raw model outputs to unique integer positions 1..N.

    Ranks the raw predictions (lower = better position) and assigns
    integer positions with no ties. Using kind="stable" ensures
    tie-breaking is deterministic.
    """
    # argsort of argsort gives the rank (0-indexed)
    order = raw_predictions.argsort(kind="stable").argsort(kind="stable")
    return [int(rank) + 1 for rank in order]


def store_predictions(
    engine: Engine,
    race_id: int,
    model_version_id: int,
    predictions: pd.DataFrame,
) -> int:
    """Insert prediction rows into the predictions table.

    Uses ON CONFLICT to allow re-running without creating duplicates.
    Returns the number of rows upserted.
    """
    now = datetime.now(timezone.utc)
    rows = [
        {
            "race_id": race_id,
            "model_version_id": model_version_id,
            "driver_id": int(rec["driver_id"]),
            "constructor_id": int(rec["constructor_id"]),
            "predicted_position": int(rec["predicted_position"]),
            "confidence_score": None,
            "created_at": now,
        }
        for rec in predictions.to_dict("records")
    ]

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO predictions
                    (race_id, model_version_id, driver_id, constructor_id,
                     predicted_position, confidence_score, created_at)
                VALUES
                    (:race_id, :model_version_id, :driver_id, :constructor_id,
                     :predicted_position, :confidence_score, :created_at)
                ON CONFLICT (race_id, model_version_id, driver_id) DO UPDATE
                    SET predicted_position = EXCLUDED.predicted_position,
                        confidence_score   = EXCLUDED.confidence_score,
                        created_at         = EXCLUDED.created_at,
                        constructor_id     = EXCLUDED.constructor_id
                """
            ),
            rows,
        )
    logger.info(
        "Stored %d predictions for race_id=%d, model_version_id=%d",
        len(rows),
        race_id,
        model_version_id,
    )
    return len(rows)


def run(
    race_id: int,
    model_version_id: int,
    model_path: Path = ARTIFACTS_DIR / "model_v1.json",
    engine: Engine | None = None,
) -> pd.DataFrame:
    """End-to-end prediction pipeline for a single race.

    Returns a DataFrame with driver_id, constructor_id, and predicted_position.
    """
    if engine is None:
        engine = get_engine()

    model = load_model(model_path)
    features_df = load_features(engine, race_id)
    prepared = prepare_features(features_df)

    missing = [c for c in FEATURE_COLS if c not in prepared.columns]
    if missing:
        raise ValueError(f"Feature columns missing from loaded data: {missing}")

    raw_preds = model.predict(prepared[FEATURE_COLS])
    positions = normalise_positions(raw_preds)

    features_df = features_df.reset_index(drop=True)
    features_df["predicted_position"] = positions

    result = features_df[["driver_id", "constructor_id", "predicted_position"]]
    store_predictions(engine, race_id, model_version_id, result)

    logger.info("Predictions complete for race_id=%d", race_id)
    return result


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Generate pre-race predictions for a given race.")
    parser.add_argument(
        "--race-id",
        type=int,
        required=True,
        help="ID of the race to predict",
    )
    parser.add_argument(
        "--model-version-id",
        type=int,
        required=True,
        help="ID of the model version to use",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=ARTIFACTS_DIR / "model_v1.json",
        help="Path to the trained model artifact",
    )
    args = parser.parse_args()

    run(
        race_id=args.race_id,
        model_version_id=args.model_version_id,
        model_path=args.model_path,
    )


if __name__ == "__main__":
    main()
