from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, contains_eager

from api.database import get_db
from api.models.orm import ModelVersion, Race
from api.schemas.models import ModelVersionItem

router = APIRouter()


@router.get("/model-versions", response_model=list[ModelVersionItem])
def list_model_versions(season: int, db: Session = Depends(get_db)):
    versions = (
        db.query(ModelVersion)
        .join(Race, ModelVersion.triggered_by_race_id == Race.id)
        .options(contains_eager(ModelVersion.triggered_by_race))
        .filter(Race.season == season)
        .order_by(ModelVersion.trained_at)
        .all()
    )
    return [
        ModelVersionItem(
            id=mv.id,
            trained_at=mv.trained_at,
            mae=float(mv.mae) if mv.mae is not None else None,
            round=mv.triggered_by_race.round,
            train_seasons=mv.train_seasons,
        )
        for mv in versions
    ]
