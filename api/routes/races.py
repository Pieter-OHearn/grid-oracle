from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.orm import EvaluationMetrics, Prediction, Race, RaceResult
from api.schemas.races import (
    AccuracyItem,
    ComparisonItem,
    PredictionItem,
    RaceListItem,
    ResultItem,
)

router = APIRouter()


def _get_race_or_404(race_id: int, db: Session) -> Race:
    race = db.query(Race).filter(Race.id == race_id).first()
    if not race:
        raise HTTPException(status_code=404, detail=f"Race {race_id} not found")
    return race


@router.get("/races/{season}", response_model=List[RaceListItem])
def list_races(season: int, db: Session = Depends(get_db)):
    races = db.query(Race).filter(Race.season == season).order_by(Race.round).all()
    return [
        RaceListItem(
            id=r.id,
            name=r.name,
            circuit=r.circuit.name,
            date=r.date,
            is_completed=r.is_completed,
        )
        for r in races
    ]


@router.get("/races/{race_id}/predictions", response_model=List[PredictionItem])
def get_predictions(race_id: int, db: Session = Depends(get_db)):
    _get_race_or_404(race_id, db)

    # Use the latest model version for this race
    latest_model_version_id = (
        db.query(func.max(Prediction.model_version_id))
        .filter(Prediction.race_id == race_id)
        .scalar()
    )
    if latest_model_version_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"No predictions found for race {race_id}",
        )

    preds = (
        db.query(Prediction)
        .filter(
            Prediction.race_id == race_id,
            Prediction.model_version_id == latest_model_version_id,
        )
        .order_by(Prediction.predicted_position)
        .all()
    )
    return [
        PredictionItem(
            driver=p.driver.full_name,
            constructor=p.constructor.name,
            predicted_position=p.predicted_position,
            confidence_score=(
                float(p.confidence_score) if p.confidence_score is not None else None
            ),
        )
        for p in preds
    ]


@router.get("/races/{race_id}/results", response_model=List[ResultItem])
def get_results(race_id: int, db: Session = Depends(get_db)):
    _get_race_or_404(race_id, db)

    results = (
        db.query(RaceResult)
        .filter(RaceResult.race_id == race_id)
        .order_by(RaceResult.finish_position)
        .all()
    )
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No results found for race {race_id}",
        )

    return [
        ResultItem(
            driver=r.driver.full_name,
            constructor=r.constructor.name,
            finish_position=r.finish_position,
            grid_position=r.grid_position,
            status=r.status,
        )
        for r in results
    ]


@router.get("/races/{race_id}/comparison", response_model=List[ComparisonItem])
def get_comparison(race_id: int, db: Session = Depends(get_db)):
    _get_race_or_404(race_id, db)

    latest_model_version_id = (
        db.query(func.max(Prediction.model_version_id))
        .filter(Prediction.race_id == race_id)
        .scalar()
    )
    if latest_model_version_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"No predictions found for race {race_id}",
        )

    preds = (
        db.query(Prediction)
        .filter(
            Prediction.race_id == race_id,
            Prediction.model_version_id == latest_model_version_id,
        )
        .all()
    )
    results_by_driver = {
        r.driver_id: r
        for r in db.query(RaceResult).filter(RaceResult.race_id == race_id).all()
    }

    items = []
    for p in sorted(preds, key=lambda x: x.predicted_position):
        result = results_by_driver.get(p.driver_id)
        finish_pos = result.finish_position if result else None
        delta = (
            p.predicted_position - finish_pos
            if finish_pos is not None
            else None
        )
        items.append(
            ComparisonItem(
                driver=p.driver.full_name,
                constructor=p.constructor.name,
                predicted_position=p.predicted_position,
                finish_position=finish_pos,
                position_delta=delta,
            )
        )
    return items


@router.get("/seasons/{season}/accuracy", response_model=List[AccuracyItem])
def get_season_accuracy(season: int, db: Session = Depends(get_db)):
    metrics = (
        db.query(EvaluationMetrics)
        .join(EvaluationMetrics.race)
        .filter(Race.season == season, Race.is_completed.is_(True))
        .order_by(Race.round)
        .all()
    )
    return [
        AccuracyItem(
            race_id=m.race_id,
            race_name=m.race.name,
            evaluated_at=m.evaluated_at,
            top3_accuracy=(
                float(m.top3_accuracy) if m.top3_accuracy is not None else None
            ),
            exact_position_accuracy=(
                float(m.exact_position_accuracy)
                if m.exact_position_accuracy is not None
                else None
            ),
            mean_position_error=(
                float(m.mean_position_error)
                if m.mean_position_error is not None
                else None
            ),
        )
        for m in metrics
    ]
