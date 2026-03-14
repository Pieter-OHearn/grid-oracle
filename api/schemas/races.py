import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RaceListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    circuit: str
    date: datetime.date
    is_completed: bool


class PredictionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver: str
    constructor: str
    predicted_position: int
    confidence_score: Optional[float]


class ResultItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver: str
    constructor: str
    finish_position: Optional[int]
    grid_position: Optional[int]
    status: str


class ComparisonItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver: str
    constructor: str
    predicted_position: int
    finish_position: Optional[int]
    position_delta: Optional[int]


class AccuracyItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    race_id: int
    race_name: str
    evaluated_at: datetime.datetime
    top3_accuracy: Optional[float]
    exact_position_accuracy: Optional[float]
    mean_position_error: Optional[float]
