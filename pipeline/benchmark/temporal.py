"""Fail-closed feature boundaries; archived flags cannot grant as-of eligibility."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from pipeline.dataset.historical import FeatureHorizon, FeatureRegistry

CURRENT_QUALIFYING_FEATURES = frozenset(
    {"qualifying_position", "qualifying_normalized_position", "missing__qualifying"}
)


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


def validate_features(
    frame: pd.DataFrame, horizon: str, *, evidence: dict | None = None, dataset: dict | None = None
) -> None:
    if frame.columns.has_duplicates:
        raise TemporalViolation("duplicate feature columns")
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
        if dataset is None:
            raise TemporalViolation("as-of evidence needs pinned race times")
        validate_asof(frame, horizon, registry, evidence, dataset)


def validate_asof(frame: pd.DataFrame, horizon: str, registry: FeatureRegistry, evidence: dict, dataset: dict) -> None:
    names = {d.name for d in registry.enabled_for(FeatureHorizon(horizon))} & set(frame.columns)
    races = {race["race"]: race for race in dataset["races"]}
    for row in frame.to_dict("records"):
        key = f"{row['race_key']}/{row['driver_identity_key']}"
        proof = evidence.get(key)
        if not proof or row["asof_eligible"] is not True:
            raise TemporalViolation("entry has no verified as-of evidence")
        if row["entry_provenance"] != "verified_entry_list":
            raise TemporalViolation("result-reconstructed entry list is not as-of eligible")
        cutoff = timestamp(row["cutoff"])
        race = races.get(row["race_key"])
        if race is None or row["driver_identity_key"] not in race["drivers"]:
            raise TemporalViolation("entry absent from pinned race")
        first_session, race_start = pinned_times(proof, race)
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
    is_qualifying = name in CURRENT_QUALIFYING_FEATURES and horizon == "post_qualifying"
    if not is_qualifying and timestamp(proof["event_at"]) >= first_session:
        raise TemporalViolation(f"current/future race target in historical feature: {name}")


def pinned_times(proof: dict, race: dict) -> tuple[datetime, datetime]:
    race_start = timestamp(race["event_at"])
    if timestamp(proof.get("race_start_at")) != race_start:
        raise TemporalViolation("proof race time differs from pinned race")
    if race.get("first_competitive_session_at") is None:
        raise TemporalViolation("pinned first competitive session unavailable; as-of use is forbidden")
    first_session = timestamp(race["first_competitive_session_at"])
    if timestamp(proof.get("first_competitive_session_at")) != first_session:
        raise TemporalViolation("proof first session differs from pinned race")
    return first_session, race_start
