"""Train an XGBoost regression model to predict F1 finishing positions."""

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import Integer, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY as PgArray
from sqlalchemy.engine import Engine

from pipeline.ingest.upsert_helpers import get_engine
from pipeline.ml.features import ARTIFACTS_DIR, prepare_features
from pipeline.ml.xgb_compat import XGBRegressor

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
    triggered_by_race_id: int | None = None,
) -> int:
    """Insert a row into model_versions and return the new id."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO model_versions
                    (name, trained_at, training_races_count, mae, notes,
                     train_seasons, test_season, triggered_by_race_id)
                VALUES (:name, :trained_at, :count, :mae, :notes,
                        :train_seasons, :test_season, :triggered_by_race_id)
                RETURNING id
                """
            ).bindparams(bindparam("train_seasons", type_=PgArray(Integer))),
            {
                "name": name,
                "trained_at": datetime.now(timezone.utc),
                "count": training_races_count,
                "mae": float(mae),
                "notes": f"MAE={mae:.4f}; train={train_seasons}, test={test_seasons}",
                "train_seasons": train_seasons,
                "test_season": test_seasons[0] if test_seasons else None,
                "triggered_by_race_id": triggered_by_race_id,
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("INSERT INTO model_versions returned no row")
    model_version_id = row[0]
    logger.info("Inserted model_versions row id=%d", model_version_id)
    return model_version_id


def update_artifact_path(engine: Engine, model_version_id: int, artifact_path: Path) -> None:
    """Record the artifact path for a model_versions row."""
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE model_versions SET artifact_path = :path WHERE id = :id"),
            {"path": str(artifact_path), "id": model_version_id},
        )
    if result.rowcount == 0:
        raise RuntimeError(f"update_artifact_path: no model_versions row found with id={model_version_id}")
    logger.info("Recorded artifact_path=%s for model_version_id=%d", artifact_path, model_version_id)


def _delete_model_version(engine: Engine, model_version_id: int) -> None:
    """Delete a model_versions row. Used to roll back an orphaned insert on failure."""
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM model_versions WHERE id = :id"),
            {"id": model_version_id},
        )
    logger.warning("Rolled back model_versions row id=%d after artifact save failure", model_version_id)


def get_available_seasons(engine: Engine) -> list[int]:
    """Return all seasons that have at least one completed race in the DB."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT season FROM races WHERE is_completed = TRUE ORDER BY season")
        ).fetchall()
    return [row[0] for row in rows]


def run(
    data_dir: Path = DATA_DIR,
    artifact_path: Path | None = None,
    engine: Engine | None = None,
    train_seasons: list[int] | None = None,
    test_seasons: list[int] | None = None,
    triggered_by_race_id: int | None = None,
) -> int:
    """End-to-end training pipeline.

    When train_seasons or test_seasons is None, seasons are derived from the
    database via get_available_seasons(): all but the last go to training,
    the last goes to testing. Raises ValueError if seasons overlap or fewer
    than two completed seasons exist.

    When artifact_path is None, the path is auto-derived as
    ``ARTIFACTS_DIR/model_v{model_version_id}.json`` after the DB row is
    inserted. Pass an explicit artifact_path to override this behaviour.
    """
    if engine is None:
        engine = get_engine()

    if train_seasons is None or test_seasons is None:
        available = get_available_seasons(engine)
        if len(available) < 2:
            raise ValueError(f"Need at least 2 completed seasons; found {available}")
        if train_seasons is None:
            train_seasons = available[:-1]
        if test_seasons is None:
            test_seasons = [available[-1]]

    overlap = set(train_seasons) & set(test_seasons)
    if overlap:
        raise ValueError(f"Seasons appear in both train and test splits: {sorted(overlap)}")

    features_df = load_feature_parquets(data_dir)
    df = attach_targets(features_df, engine)

    model, mae, training_races_count = train_model(
        df,
        train_seasons=train_seasons,
        test_seasons=test_seasons,
    )

    model_version_id = insert_model_version(
        engine,
        name="xgb_v1",
        training_races_count=training_races_count,
        mae=mae,
        train_seasons=train_seasons,
        test_seasons=test_seasons,
        triggered_by_race_id=triggered_by_race_id,
    )

    if artifact_path is None:
        artifact_path = ARTIFACTS_DIR / f"model_v{model_version_id}.json"

    try:
        save_model(model, artifact_path)
        update_artifact_path(engine, model_version_id, artifact_path)
    except Exception:
        _delete_model_version(engine, model_version_id)
        raise

    logger.info("Training complete — model_version_id=%d", model_version_id)
    return model_version_id


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
        default=None,
        help="Path to save the trained model (default: auto-derived from model_version_id)",
    )
    parser.add_argument(
        "--train-seasons",
        type=int,
        nargs="+",
        default=None,
        metavar="YEAR",
        help="Seasons to use for training (default: auto-derived from DB — all but the most recent completed season)",
    )
    parser.add_argument(
        "--test-seasons",
        type=int,
        nargs="+",
        default=None,
        metavar="YEAR",
        help="Seasons to use for evaluation (default: auto-derived from DB — the most recent completed season)",
    )
    args = parser.parse_args()

    run(
        data_dir=args.data_dir,
        artifact_path=args.output,
        train_seasons=args.train_seasons,
        test_seasons=args.test_seasons,
    )


if __name__ == "__main__":
    main()
