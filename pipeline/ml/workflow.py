"""Shared ML workflow helpers used by the scheduler and bootstrap."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.features.builder import build_features_for_race, export_parquet
from pipeline.ml import evaluate as ml_evaluate
from pipeline.ml import predict as ml_predict
from pipeline.ml import train as ml_train

logger = logging.getLogger(__name__)


def _get_latest_model_version_id_for_race(race_id: int, engine: Engine) -> int | None:
    """Return the model_version used for the most recent predictions of a race."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT model_version_id FROM predictions WHERE race_id = :rid ORDER BY created_at DESC LIMIT 1"),
            {"rid": race_id},
        ).fetchone()
    return row[0] if row else None


def _get_remaining_race_ids(season: int, engine: Engine) -> list[int]:
    """Return IDs of races that have not completed yet (date > today, is_completed = FALSE)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id FROM races WHERE season = :season AND is_completed = FALSE AND date > :today ORDER BY date"
            ),
            {"season": season, "today": datetime.now(timezone.utc).date()},
        ).fetchall()
    return [row[0] for row in rows]


def predict_remaining_races(season: int, model_version_id: int, engine: Engine) -> None:
    """Generate predictions for all future races in season using the given model."""
    remaining_ids = _get_remaining_race_ids(season, engine)
    logger.info(
        "workflow: predicting %d remaining races with model_version_id=%d",
        len(remaining_ids),
        model_version_id,
    )
    for rid in remaining_ids:
        try:
            ml_predict.run(race_id=rid, model_version_id=model_version_id, engine=engine)
        except Exception:
            logger.exception("workflow: prediction failed for race_id=%d", rid)


def retrain_model(race_id: int, engine: Engine) -> int:
    """Build features for race_id, export Parquet, and retrain model tagged to that race."""
    df = build_features_for_race(race_id, engine)
    if not df.empty:
        export_parquet(df, race_id)
    new_model_version_id = ml_train.run(engine=engine, triggered_by_race_id=race_id)
    logger.info("workflow: retrain complete — model_version_id=%d (race_id=%d)", new_model_version_id, race_id)
    return new_model_version_id


def evaluate_race(race_id: int, engine: Engine) -> None:
    """Evaluate the completed race against its pre-race predictions, if any."""
    old_model_version_id = _get_latest_model_version_id_for_race(race_id, engine)
    if old_model_version_id is None:
        logger.info("workflow: skipping evaluation — no predictions for race_id=%d", race_id)
        return
    try:
        ml_evaluate.run(race_id=race_id, model_version_id=old_model_version_id, engine=engine)
    except Exception:
        logger.exception(
            "workflow: evaluation failed for race_id=%d model_version_id=%d",
            race_id,
            old_model_version_id,
        )


def post_race_pipeline(race_id: int, season: int, engine: Engine) -> int | None:
    """Retrain, evaluate, and refresh predictions after a race has completed.

    Returns the new model_version_id when retraining succeeds, otherwise None.
    """
    logger.info("post_race_pipeline: starting (race_id=%d, season=%d)", race_id, season)
    try:
        try:
            new_model_version_id = retrain_model(race_id, engine)
        except ValueError as exc:
            logger.warning("post_race_pipeline: skipping retrain for race_id=%d — %s", race_id, exc)
            return None

        evaluate_race(race_id, engine)
        predict_remaining_races(season, new_model_version_id, engine)
        logger.info(
            "post_race_pipeline: complete — model_version_id=%d, season=%d",
            new_model_version_id,
            season,
        )
        return new_model_version_id
    except Exception:
        logger.exception(
            "post_race_pipeline: failed for race_id=%d — stale predictions remain live",
            race_id,
        )
        return None
