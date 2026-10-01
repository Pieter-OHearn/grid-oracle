"""The public v1 surface only contains GET resources and approved projections."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.database import get_db
from api.schemas.public import (
    ErrorResponse,
    Event,
    EventIndex,
    ForecastSelection,
    Horizon,
    PublishedRun,
    RunIndex,
    Season,
    SeasonIndex,
    SessionIndex,
)
from api.services import public

router = APIRouter(
    prefix="/api/v1",
    tags=["public-v1"],
    responses={code: {"model": ErrorResponse} for code in (404, 422, 503)},
)


@router.get("/seasons", response_model=SeasonIndex)
def seasons(db: Session = Depends(get_db)):
    return SeasonIndex(seasons=public.seasons(db))


@router.get("/seasons/{season}", response_model=Season)
def season_resource(season: int, db: Session = Depends(get_db)):
    public.require_season(db, season)
    return next(item for item in public.seasons(db) if item.year == season)


@router.get("/seasons/{season}/events", response_model=EventIndex)
def events(season: int, db: Session = Depends(get_db)):
    return EventIndex(season=season, events=public.events(db, season))


@router.get("/seasons/{season}/events/{event_id}", response_model=Event)
def event_resource(season: int, event_id: int, db: Session = Depends(get_db)):
    return public.project_event(db, public.require_event(db, season, event_id))


@router.get("/seasons/{season}/events/{event_id}/sessions", response_model=SessionIndex)
def sessions(season: int, event_id: int, db: Session = Depends(get_db)):
    return SessionIndex(
        season=season, event_id=event_id, sessions=public.sessions(db, season, event_id)
    )


@router.get(
    "/seasons/{season}/events/{event_id}/forecast", response_model=ForecastSelection
)
def forecast(
    season: int, event_id: int, horizon: Horizon, db: Session = Depends(get_db)
):
    return public.selection(db, season, event_id, horizon)


@router.get("/seasons/{season}/events/{event_id}/runs", response_model=RunIndex)
def runs(season: int, event_id: int, db: Session = Depends(get_db)):
    return RunIndex(
        season=season,
        event_id=event_id,
        runs=public.published_runs(db, season, event_id),
    )


@router.get(
    "/seasons/{season}/events/{event_id}/runs/{run_id}", response_model=PublishedRun
)
def run_resource(
    season: int, event_id: int, run_id: str, db: Session = Depends(get_db)
):
    runs = public.published_runs(db, season, event_id, run_id=run_id)
    if not runs:
        raise public.PublicReadError("not_found", "Published run not found")
    return runs[0]


@router.get("/legacy/races/{race_id}", response_model=Event)
def legacy_race(race_id: int, db: Session = Depends(get_db)):
    rows = public.rows(db, "SELECT season FROM races WHERE id = :id", id=race_id)
    if not rows:
        raise public.PublicReadError("not_found", "Legacy race not found")
    return public.project_event(
        db, public.require_event(db, rows[0]["season"], race_id)
    )
