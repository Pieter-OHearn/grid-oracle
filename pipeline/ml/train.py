"""Train an XGBoost regression model to predict F1 finishing positions."""

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from xgboost import XGBRegressor

from pipeline.ingest.upsert_helpers import get_engine
from pipeline.ml.features import ARTIFACTS_DIR, prepare_features

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

FEATURE_COLS = [
    "grid_position",
    "driver_avg_position_last_3_races",
    "driver_avg_position_at_circuit",
    "driver_podium_rate_at_circuit",
    "constructor_avg_position_last_3_races",
    "constructor_avg_position_at_circuit",
    "circuit_type",
    "is_wet_race_forecast",
    "driver_wet_race_avg_position",
    "constructor_wet_race_avg_position",
    "driver_season_avg_position",
    "championship_position",
]

TARGET_COL = "finish_position"


def load_feature_parquets(data_dir: Path) -> pd.DataFrame:
    """Load and concatenate all feature Parquet files."""
    parquet_files = sorted(data_dir.glob("features_*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No feature Parquet files found in {data_dir}")
    logger.info("Loading %d Parquet files from %s", len(parquet_files), data_dir)
    dfs = [pd.read_parquet(p) for p in parquet_files]
    return pd.concat(dfs, ignore_index=True)


def attach_targets(features_df: pd.DataFrame, engine: Engine) -> pd.DataFrame:
    """Join features with finish_position and season from the database.

    Only keeps rows for completed races that have a known finish position.
    """
    race_ids = features_df["race_id"].unique().tolist()
    with engine.connect() as conn:
        results = pd.read_sql(
            text(
                """
                SELECT rr.race_id, rr.driver_id, rr.finish_position, r.season
                FROM race_results rr
                JOIN races r ON r.id = rr.race_id
                WHERE r.is_completed = TRUE
                  AND rr.finish_position IS NOT NULL
                  AND rr.race_id = ANY(:race_ids)
                """
            ),
            conn,
            params={"race_ids": race_ids},
        )
    merged = features_df.merge(results, on=["race_id", "driver_id"], how="inner")
    logger.info(
        "Merged dataset: %d rows (%d dropped — no result)",
        len(merged),
        len(features_df) - len(merged),
    )
    return merged


# prepare_features is imported from pipeline.ml.features above and re-exported
# here so that existing callers (e.g. test_train.py) can still import it from
# this module without change.


def train_model(
    df: pd.DataFrame,
    train_seasons: list[int],
    test_seasons: list[int],
) -> tuple[XGBRegressor, float, int]:
    """Train an XGBRegressor and return (model, mae, training_race_count).

    Trains on data from ``train_seasons`` and evaluates on ``test_seasons``.
    """
    df = prepare_features(df)

    train_mask = df["season"].isin(train_seasons)
    test_mask = df["season"].isin(test_seasons)

    train_df = df[train_mask]
    test_df = df[test_mask]

    if train_df.empty:
        raise ValueError(f"No training data for seasons {train_seasons}")
    if test_df.empty:
        raise ValueError(f"No test data for seasons {test_seasons}")

    X_train = train_df[FEATURE_COLS]
    y_train = train_df[TARGET_COL]
    X_test = test_df[FEATURE_COLS]
    y_test = test_df[TARGET_COL]

    model = XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        enable_categorical=True,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = float((abs(preds - y_test)).mean())

    training_race_count = int(train_df["race_id"].nunique())

    logger.info("Train seasons: %s (%d races)", train_seasons, training_race_count)
    logger.info("Test seasons:  %s (%d races)", test_seasons, int(test_df["race_id"].nunique()))
    logger.info("Mean absolute position error: %.4f", mae)

    return model, mae, training_race_count


def save_model(model: XGBRegressor, path: Path) -> None:
    """Save the trained model to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(path))
    logger.info("Model saved to %s", path)


def insert_model_version(
    engine: Engine,
    name: str,
    training_races_count: int,
    mae: float,
    train_seasons: list[int],
    test_seasons: list[int],
) -> int:
    """Insert a row into model_versions and return the new id."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO model_versions
                    (name, trained_at, training_races_count, mae, notes)
                VALUES (:name, :trained_at, :count, :mae, :notes)
                RETURNING id
                """
            ),
            {
                "name": name,
                "trained_at": datetime.now(timezone.utc),
                "count": training_races_count,
                "mae": float(mae),
                "notes": f"MAE={mae:.4f}; train={train_seasons}, test={test_seasons}",
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("INSERT INTO model_versions returned no row")
    model_version_id = row[0]
    logger.info("Inserted model_versions row id=%d", model_version_id)
    return model_version_id


def run(
    data_dir: Path = DATA_DIR,
    artifact_path: Path = ARTIFACTS_DIR / "model_v1.json",
    engine: Engine | None = None,
) -> None:
    """End-to-end training pipeline."""
    if engine is None:
        engine = get_engine()

    features_df = load_feature_parquets(data_dir)
    df = attach_targets(features_df, engine)

    train_seasons = [2022, 2023]
    test_seasons = [2024]

    model, mae, training_races_count = train_model(
        df,
        train_seasons=train_seasons,
        test_seasons=test_seasons,
    )

    save_model(model, artifact_path)

    model_version_id = insert_model_version(
        engine,
        name="xgb_v1",
        training_races_count=training_races_count,
        mae=mae,
        train_seasons=train_seasons,
        test_seasons=test_seasons,
    )
    logger.info("Training complete — model_version_id=%d", model_version_id)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Train XGBoost baseline model.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help="Directory containing feature Parquet files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ARTIFACTS_DIR / "model_v1.json",
        help="Path to save the trained model",
    )
    args = parser.parse_args()

    run(data_dir=args.data_dir, artifact_path=args.output)


if __name__ == "__main__":
    main()
