from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, contains_eager, joinedload

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


def _latest_model_version_id(race_id: int, db: Session) -> int:
    # Model version IDs are monotonically increasing;
    # max ID == most recently trained version
    mv_id = (
        db.query(func.max(Prediction.model_version_id))
        .filter(Prediction.race_id == race_id)
        .scalar()
    )
    if mv_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"No predictions found for race {race_id}",
        )
    return mv_id


@router.get("/races/{season}", response_model=list[RaceListItem])
def list_races(season: int, db: Session = Depends(get_db)):
    races = (
        db.query(Race)
        .options(joinedload(Race.circuit))
        .filter(Race.season == season)
        .order_by(Race.round)
        .all()
    )
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


@router.get("/races/{race_id}/predictions", response_model=list[PredictionItem])
def get_predictions(race_id: int, db: Session = Depends(get_db)):
    _get_race_or_404(race_id, db)
    mv_id = _latest_model_version_id(race_id, db)

    preds = (
        db.query(Prediction)
        .options(joinedload(Prediction.driver), joinedload(Prediction.constructor))
        .filter(Prediction.race_id == race_id, Prediction.model_version_id == mv_id)
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


@router.get("/races/{race_id}/results", response_model=list[ResultItem])
def get_results(race_id: int, db: Session = Depends(get_db)):
    _get_race_or_404(race_id, db)

    results = (
        db.query(RaceResult)
        .options(joinedload(RaceResult.driver), joinedload(RaceResult.constructor))
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


@router.get("/races/{race_id}/comparison", response_model=list[ComparisonItem])
def get_comparison(race_id: int, db: Session = Depends(get_db)):
    _get_race_or_404(race_id, db)
    mv_id = _latest_model_version_id(race_id, db)

    preds = (
        db.query(Prediction)
        .options(joinedload(Prediction.driver), joinedload(Prediction.constructor))
        .filter(Prediction.race_id == race_id, Prediction.model_version_id == mv_id)
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
        delta = p.predicted_position - finish_pos if finish_pos is not None else None
        items.append(
            ComparisonItem(
                driver=p.driver.full_name,
                constructor=p.constructor.name,
                predicted_position=p.predicted_position,
                confidence_score=(
                    float(p.confidence_score)
                    if p.confidence_score is not None
                    else None
                ),
                finish_position=finish_pos,
                position_delta=delta,
                status=result.status if result else None,
                fastest_lap=result.fastest_lap if result else False,
            )
        )
    return items


@router.get("/seasons/{season}/accuracy", response_model=list[AccuracyItem])
def get_season_accuracy(season: int, db: Session = Depends(get_db)):
    metrics = (
        db.query(EvaluationMetrics)
        .join(EvaluationMetrics.race)
        .options(contains_eager(EvaluationMetrics.race))
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
