"""Stored metric projections. Never computes scores or passes through manifests."""

import math
from pathlib import Path

from api.schemas.public import (
    EventPerformance,
    HistoricalPerformance,
    LivePerformance,
    PerformanceMetric,
    PublicEvaluation,
    ResultCorrection,
)
from api.services import public

# Metric meanings are versioned, not caller-supplied prose.
METRICS = {
    "winner_log_loss": ("Winner log loss", "official race winner", "loss"),
    "winner_hit": (
        "Winner pick hit rate",
        "first predicted entrant is official winner",
        "fraction",
    ),
    "winner_brier": (
        "Winner Brier score",
        "official race winner across full field",
        "loss",
    ),
    "rank_mae": (
        "Classified rank MAE",
        "internal rank among classified entrants",
        "positions",
    ),
    "rank_correlation": (
        "Classified rank correlation",
        "internal rank among classified entrants",
        "correlation",
    ),
    "top3_overlap": (
        "Official top-three set overlap",
        "membership of official top-three set, regardless of order",
        "fraction",
    ),
    "top10_overlap": (
        "Official top-ten set overlap",
        "membership of official top-ten set, regardless of order",
        "fraction",
    ),
    "ece": (
        "Winner calibration error",
        "winner reliability over ten fixed bins",
        "fraction",
    ),
}


def metric_projection(values, counts):
    result = []
    for key, (label, outcome, unit) in METRICS.items():
        value = values.get(key)
        count = counts.get(key)
        if value is not None and (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or (unit == "fraction" and not 0 <= value <= 1)
            or (unit in {"positions", "loss"} and value < 0)
            or (unit == "correlation" and not -1 <= value <= 1)
        ):
            raise public.PublicReadError(
                "invalid_publication", "Stored evaluation is invalid", 503
            )
        if count is not None and (type(count) is not int or count < 0):
            raise public.PublicReadError(
                "invalid_publication", "Stored evaluation count is invalid", 503
            )
        # Unknown denominators cannot support public performance claims.
        if count is None or count == 0:
            value = None
        result.append(
            PerformanceMetric(
                key=key,
                label=label,
                outcome=outcome,
                value=value,
                unit=unit,
                observations=count,
            )
        )
    return result


def historical():
    return HistoricalPerformance.model_validate_json(
        (
            Path(__file__).parent.parent / "data" / "historical-performance.json"
        ).read_text()
    )


def event_performance(db, season, event_id, horizon):
    event = public.require_event(db, season, event_id)
    runs = public.published_runs(db, season, event_id, horizon=horizon)
    run = runs[0] if runs else None
    corrections = []
    for row in public.rows(
        db,
        "SELECT id, revision, recorded_at, is_official FROM result_revisions "
        "WHERE race_id = :event ORDER BY revision",
        event=event_id,
    ):
        evaluations = []
        if run:
            for record in public.rows(
                db,
                "SELECT metrics, evaluator_manifest, evaluated_at FROM evaluation_runs "
                "WHERE forecast_run_id = :run AND result_revision_id = :result "
                "ORDER BY evaluated_at",
                run=run.run_id,
                result=row["id"],
            ):
                manifest = public.decoded(record["evaluator_manifest"])
                # Explicit producer opt-in to metric meanings and denominators.
                # Generic WP03/legacy metrics cannot establish this contract.
                if (
                    not isinstance(manifest, dict)
                    or manifest.get("public_contract") != "wp12-v1"
                ):
                    continue
                payload = public.decoded(record["metrics"])
                if (
                    not isinstance(payload, dict)
                    or not isinstance(payload.get("values"), dict)
                    or not isinstance(payload.get("observations"), dict)
                ):
                    raise public.PublicReadError(
                        "invalid_publication", "Stored evaluation is invalid", 503
                    )
                evaluations.append(
                    PublicEvaluation(
                        evaluated_at=public.timestamp(record["evaluated_at"]),
                        run_id=run.run_id,
                        result_revision=row["revision"],
                        metrics=metric_projection(
                            payload["values"], payload["observations"]
                        ),
                    )
                )
        corrections.append(
            ResultCorrection(
                revision=row["revision"],
                recorded_at=public.timestamp(row["recorded_at"]),
                official=bool(row["is_official"]),
                change="Initial recorded result"
                if not corrections
                else "Result correction recorded",
                evaluations=evaluations,
            )
        )
    return EventPerformance(
        season=season,
        event_id=event_id,
        event_name=event["name"],
        round=event["round"],
        horizon=horizon,
        run_id=run.run_id if run else None,
        corrections=corrections,
        status="no_published_forecast"
        if not run
        else "stored_evaluation"
        if any(c.evaluations for c in corrections)
        else "evaluation_unavailable",
    )


def live(db, season, horizon):
    return LivePerformance(
        season=season,
        horizon=horizon,
        events=[
            event_performance(db, season, e.id, horizon)
            for e in public.events(db, season)
        ],
    )
