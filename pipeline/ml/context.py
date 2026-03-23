"""Shared pre-weekend prediction context helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PREWEEKEND_CONTEXT = "preweekend"
PREWEEKEND_THURSDAY_HOUR_UTC = 9

SUPPORTED_PREDICTION_CONTEXTS = {PREWEEKEND_CONTEXT}


def validate_prediction_context(context: str) -> str:
    """Return a supported prediction context or raise ValueError."""
    if context not in SUPPORTED_PREDICTION_CONTEXTS:
        supported = ", ".join(sorted(SUPPORTED_PREDICTION_CONTEXTS))
        raise ValueError(f"Unsupported prediction context {context!r}; expected one of: {supported}")
    return context


def compute_preweekend_cutoff(race_date: date) -> datetime:
    """Return the Thursday 09:00 UTC cutoff for pre-weekend snapshots."""
    days_back = (race_date.weekday() - 3) % 7
    thursday = race_date - timedelta(days=days_back)
    return datetime(
        thursday.year,
        thursday.month,
        thursday.day,
        PREWEEKEND_THURSDAY_HOUR_UTC,
        0,
        0,
        tzinfo=timezone.utc,
    )


def feature_parquet_filename(race_id: int, context: str = PREWEEKEND_CONTEXT) -> str:
    """Return the context-specific feature snapshot filename for a race."""
    validate_prediction_context(context)
    return f"features_{context}_{race_id}.parquet"


def feature_parquet_glob(context: str = PREWEEKEND_CONTEXT) -> str:
    """Return the glob used to load context-specific feature snapshots."""
    validate_prediction_context(context)
    return f"features_{context}_*.parquet"


def feature_parquet_path(data_dir: Path, race_id: int, context: str = PREWEEKEND_CONTEXT) -> Path:
    """Return the context-specific feature snapshot path for a race."""
    return data_dir / feature_parquet_filename(race_id, context)
