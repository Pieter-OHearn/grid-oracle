"""Shared ML utilities for the pipeline.ml package."""

from pathlib import Path

import pandas as pd

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encode categorical columns and convert booleans for XGBoost.

    Used by both the training and prediction pipelines to ensure
    identical pre-processing at train and inference time.
    """
    df = df.copy()
    df["circuit_type"] = df["circuit_type"].astype("category")
    df["is_wet_race_forecast"] = df["is_wet_race_forecast"].astype(int)
    return df
