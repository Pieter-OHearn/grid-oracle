"""Fail-closed feature boundaries; archived flags cannot grant as-of eligibility."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from pipeline.dataset.historical import FeatureHorizon, FeatureRegistry


class TemporalViolation(ValueError):
    pass


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
        if not result.tzinfo:
            raise ValueError("timezone required")
        return result
    except (ValueError, TypeError) as error:
        raise TemporalViolation("missing/invalid temporal evidence") from error


def validate_features(frame: pd.DataFrame, horizon: str, *, evidence: dict | None = None) -> None:
    registry = FeatureRegistry.audited_default()
    try:
        registry.validate_columns(frame, FeatureHorizon(horizon))
    except ValueError as error:
        raise TemporalViolation(str(error)) from error
    if frame.empty or not (frame.horizon == horizon).all():
        raise TemporalViolation("empty or mixed-horizon features")
    if frame.duplicated(["race_key", "driver_identity_key"]).any():
        raise TemporalViolation("duplicate race entry")
    if horizon == "pre_weekend" and not frame.missing__qualifying.eq(True).all():
        raise TemporalViolation("pre-weekend qualifying missingness leaks current session")
    if evidence is not None:
        validate_asof(frame, horizon, registry, evidence)


def validate_asof(frame: pd.DataFrame, horizon: str, registry: FeatureRegistry, evidence: dict) -> None:
    names = {d.name for d in registry.enabled_for(FeatureHorizon(horizon))} & set(frame.columns)
    for row in frame.to_dict("records"):
        key = f"{row['race_key']}/{row['driver_identity_key']}"
        proof = evidence.get(key)
        if not proof or row["asof_eligible"] is not True:
            raise TemporalViolation("entry has no verified as-of evidence")
        if row["entry_provenance"] != "verified_entry_list":
            raise TemporalViolation("result-reconstructed entry list is not as-of eligible")
        cutoff = timestamp(row["cutoff"])
        first_session = timestamp(proof.get("first_competitive_session_at"))
        race_start = timestamp(proof.get("race_start_at"))
        if first_session >= race_start:
            raise TemporalViolation("invalid session/race chronology")
        if cutoff >= race_start or (horizon == "pre_weekend" and cutoff >= first_session):
            raise TemporalViolation("forecast cutoff after horizon deadline")
        for field in ("entry_available_at", "entry_retrieved_at"):
            if timestamp(proof.get(field)) > cutoff:
                raise TemporalViolation("entry list arrived after cutoff")
        if horizon == "post_qualifying":
            if cutoff < first_session:
                raise TemporalViolation("post-qualifying cutoff before the weekend")
            for field in ("qualifying_final_at", "grid_verified_at"):
                if timestamp(proof.get(field)) > cutoff:
                    raise TemporalViolation("qualifying/grid not ready at cutoff")
        for name in names:
            validate_feature_time(name, proof.get("features", {}).get(name), cutoff, first_session, horizon)


def validate_feature_time(
    name: str, proof: dict | None, cutoff: datetime, first_session: datetime, horizon: str
) -> None:
    if not proof:
        raise TemporalViolation(f"missing feature lineage: {name}")
    for field in ("available_at", "retrieved_at", "event_at"):
        if timestamp(proof.get(field)) > cutoff:
            raise TemporalViolation(f"future {field} in {name}")
    is_qualifying = "qualifying" in name and horizon == "post_qualifying"
    if not is_qualifying and timestamp(proof["event_at"]) >= first_session:
        raise TemporalViolation(f"current/future race target in historical feature: {name}")
