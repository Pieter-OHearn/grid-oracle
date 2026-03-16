"""Shared ML utilities for the pipeline.ml package."""

from pathlib import Path

import pandas as pd

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encode categorical columns and coerce numerics for XGBoost.

    Used by both the training and prediction pipelines to ensure
    identical pre-processing at train and inference time.

    - circuit_type: label-encoded as integer (avoids XGBoost categorical API)
    - All numeric features cast to float so no object columns reach the model
    - is_wet_race_forecast: bool → int
    """
    df = df.copy()

    # Label-encode circuit_type as an integer so XGBoost treats it as numeric.
    # Using category().cat.codes converts unknown/street/permanent/etc. to 0,1,2…
    df["circuit_type"] = df["circuit_type"].astype("category").cat.codes.astype(float)

    df["is_wet_race_forecast"] = df["is_wet_race_forecast"].astype(int)

    # Coerce any int-or-None columns that pandas stores as object to float.
    # pd.to_numeric converts None/NaN to NaN (float), which XGBoost handles fine.
    _numeric_cols = [
        "grid_position",
        "driver_avg_position_last_3_races",
        "driver_avg_position_at_circuit",
        "driver_podium_rate_at_circuit",
        "constructor_avg_position_last_3_races",
        "constructor_avg_position_at_circuit",
        "driver_wet_race_avg_position",
        "constructor_wet_race_avg_position",
        "driver_season_avg_position",
        "championship_position",
    ]
    for col in _numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df
