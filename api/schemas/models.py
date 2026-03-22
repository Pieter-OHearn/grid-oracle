from datetime import datetime

from pydantic import BaseModel


class ModelVersionItem(BaseModel):
    id: int
    trained_at: datetime
    mae: float | None
    round: int | None
    train_seasons: list[int] | None

    model_config = {"from_attributes": True}
