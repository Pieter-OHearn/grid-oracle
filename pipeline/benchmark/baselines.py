"""Fixed, untuned deterministic orders and corresponding winner probabilities."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.benchmark.data import KEY
from pipeline.benchmark.temporal import validate_features


def predict(frame: pd.DataFrame, name: str, horizon: str, temperature: float) -> dict:
    validate_features(frame, horizon)
    if frame.race_key.nunique() != 1 or temperature <= 0:
        raise ValueError("baseline requires one race and a positive temperature")
    frame = frame.sort_values(KEY).copy()
    standings = frame.driver_championship_position_race_only.fillna((len(frame) + 1) / 2)
    if name == "qualifying" and horizon == "post_qualifying":
        score = frame.qualifying_position.fillna(standings)
    elif name == "standings":
        score = standings
    elif name == "recent_form":
        score = frame[["driver_finish_mean_last_3", "constructor_finish_mean_last_3"]].mean(axis=1).fillna(standings)
    elif name == "uniform":
        score = pd.Series(1.0, index=frame.index)
    else:
        raise ValueError(f"baseline {name} not allowed for {horizon}")
    ranked = frame.assign(score=score).sort_values(["score", KEY])
    ordered = ranked[KEY].tolist()
    ranks = ranked["score"].rank(method="average").to_numpy() - 1
    strength = np.ones(len(ordered)) if name == "uniform" else np.exp(-ranks / temperature)
    return {"order": ordered, "winner": dict(zip(ordered, (strength / strength.sum()).tolist(), strict=True))}
