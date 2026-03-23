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
from pipeline.ml.context import PREWEEKEND_CONTEXT

logger = logging.getLogger(__name__)


def _get_latest_model_version_id_for_race(race_id: int, engine: Engine) -> int | None:
    """Return the model_version used for the most recent predictions of a race."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT model_version_id FROM predictions WHERE race_id = :rid ORDER BY created_at DESC LIMIT 1"),
            {"rid": race_id},
        ).fetchone()
    return row[0] if row else None


def _get_completed_races(engine: Engine) -> list[dict]:
    """Return completed races in strict chronological order."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, season, round, date
                FROM races
                WHERE is_completed = TRUE
                ORDER BY date, season, round
                """
            )
        ).fetchall()
    return [{"race_id": row[0], "season": row[1], "round": row[2], "date": row[3]} for row in rows]


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


def _get_cumulative_backtest_mae(through_race_id: int, engine: Engine) -> float | None:
    """Return average per-race MPE from the latest evaluated prediction of each race."""
    with engine.connect() as conn:
        cutoff_row = conn.execute(
            text("SELECT date FROM races WHERE id = :race_id"),
            {"race_id": through_race_id},
        ).fetchone()
        if cutoff_row is None:
            raise ValueError(f"Race {through_race_id} not found")

        rows = conn.execute(
            text(
                """
                SELECT mean_position_error
                FROM (
                    SELECT
                        em.mean_position_error,
                        ROW_NUMBER() OVER (
                            PARTITION BY em.race_id
                            ORDER BY em.evaluated_at DESC, em.model_version_id DESC
                        ) AS row_num
                    FROM evaluation_metrics em
                    JOIN races r ON r.id = em.race_id
                    WHERE r.date <= :cutoff_date
                      AND em.mean_position_error IS NOT NULL
                ) ranked
                WHERE row_num = 1
                """
            ),
            {"cutoff_date": cutoff_row[0]},
        ).fetchall()

    if not rows:
        return None

    values = [float(row[0]) for row in rows]
    return round(sum(values) / len(values), 4)


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
    """Export the pre-weekend snapshot for race_id and retrain through that race."""
    df = build_features_for_race(race_id, engine, context=PREWEEKEND_CONTEXT)
    if not df.empty:
        export_parquet(df, race_id, context=PREWEEKEND_CONTEXT)
    new_model_version_id = ml_train.run(
        engine=engine,
        triggered_by_race_id=race_id,
        through_race_id=race_id,
        evaluation_mae=_get_cumulative_backtest_mae(race_id, engine),
    )
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


def walk_forward_backtest(engine: Engine) -> int | None:
    """Replay completed races using only pre-weekend snapshots in chronological order."""
    completed_races = _get_completed_races(engine)
    if not completed_races:
        logger.info("walk_forward_backtest: no completed races available")
        return None

    try:
        current_model_version_id = retrain_model(completed_races[0]["race_id"], engine)
    except ValueError as exc:
        logger.warning("walk_forward_backtest: skipping initial training — %s", exc)
        return None

    logger.info(
        "walk_forward_backtest: seeded model_version_id=%d from race_id=%d",
        current_model_version_id,
        completed_races[0]["race_id"],
    )

    for race in completed_races[1:]:
        try:
            ml_predict.run(
                race_id=race["race_id"],
                model_version_id=current_model_version_id,
                engine=engine,
            )
        except Exception:
            logger.exception(
                "walk_forward_backtest: prediction failed for race_id=%d model_version_id=%d",
                race["race_id"],
                current_model_version_id,
            )

        new_model_version_id = post_race_pipeline(
            race["race_id"],
            race["season"],
            engine,
            refresh_future_predictions=False,
        )
        if new_model_version_id is not None:
            current_model_version_id = new_model_version_id

    return current_model_version_id


def post_race_pipeline(
    race_id: int,
    season: int,
    engine: Engine,
    refresh_future_predictions: bool = True,
) -> int | None:
    """Retrain, evaluate, and refresh predictions after a race has completed.

    Returns the new model_version_id when retraining succeeds, otherwise None.
    """
    logger.info("post_race_pipeline: starting (race_id=%d, season=%d)", race_id, season)
    try:
        try:
            evaluate_race(race_id, engine)
            new_model_version_id = retrain_model(race_id, engine)
        except ValueError as exc:
            logger.warning("post_race_pipeline: skipping retrain for race_id=%d — %s", race_id, exc)
            return None

        if refresh_future_predictions:
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
