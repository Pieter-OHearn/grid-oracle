import datetime

from pydantic import BaseModel


class RaceListItem(BaseModel):
    id: int
    name: str
    circuit: str
    date: datetime.date
    is_completed: bool


class PredictionItem(BaseModel):
    driver: str
    constructor: str
    predicted_position: int
    confidence_score: float | None = None


class ResultItem(BaseModel):
    driver: str
    constructor: str
    finish_position: int | None = None
    grid_position: int | None = None
    status: str


class ComparisonItem(BaseModel):
    driver: str
    constructor: str
    predicted_position: int
    confidence_score: float | None = None
    finish_position: int | None = None
    # predicted_position - finish_position; positive = predicted too high
    position_delta: int | None = None
    status: str | None = None
    fastest_lap: bool = False


class AccuracyItem(BaseModel):
    race_id: int
    race_name: str
    evaluated_at: datetime.datetime
    top3_accuracy: float | None = None
    exact_position_accuracy: float | None = None
    mean_position_error: float | None = None
