"""Read-only projections over WP02/WP03. No latest-model or legacy fallback."""

import json
import math
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.schemas.public import (
    Coverage,
    Event,
    EventSession,
    Freshness,
    PublicEntry,
    PublishedForecast,
    PublishedRun,
    Season,
    UnavailableForecast,
)


class PublicReadError(Exception):
    def __init__(self, code: str, message: str, status: int = 404):
        self.code, self.message, self.status = code, message, status


def rows(db: Session, sql: str, **params):
    return db.execute(text(sql), params).mappings().all()


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


def timestamp(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return (
        parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    )


def display_alias(db, kind, identity, on_date):
    aliases = rows(
        db,
        """SELECT provider_key FROM entity_aliases
        WHERE entity_kind = :kind AND identity_key = :identity
          AND is_display_alias = true
          AND (valid_from IS NULL OR valid_from <= :on_date)
          AND (valid_to IS NULL OR valid_to > :on_date)""",
        kind=kind,
        identity=identity,
        on_date=on_date,
    )
    # Ambiguous/missing historical labels must never fall back to today's brand.
    names = {row["provider_key"] for row in aliases}
    return next(iter(names)) if len(names) == 1 else None


def seasons(db):
    result = rows(
        db,
        "SELECT DISTINCT season FROM races UNION SELECT season "
        "FROM season_rulesets ORDER BY season DESC",
    )
    return [
        Season(
            year=row["season"],
            ruleset_version=(
                rules[0]["ruleset_version"]
                if len(
                    rules := rows(
                        db,
                        "SELECT ruleset_version FROM season_rulesets "
                        "WHERE season = :season AND is_current = true",
                        season=row["season"],
                    )
                )
                == 1
                else None
            ),
            coverage=Coverage(
                state="unknown",
                available=None,
                reason="Publication coverage is event-specific",
            ),
        )
        for row in result
    ]


def require_season(db, season):
    if not any(item.year == season for item in seasons(db)):
        raise PublicReadError("not_found", "Season not found")


def event_rows(db, season, event_id=None):
    return rows(
        db,
        """SELECT r.id, r.event_key, r.season, r.round, r.name, r.date,
                  r.lifecycle_status, r.is_completed, c.identity_key AS circuit_key
           FROM races r JOIN circuits c ON c.id = r.circuit_id
           WHERE r.season = :season"""
        + (" AND r.id = :event_id" if event_id is not None else "")
        + " ORDER BY r.round",
        season=season,
        event_id=event_id,
    )


def require_event(db, season, event_id):
    result = event_rows(db, season, event_id)
    if not result:
        raise PublicReadError("not_found", "Event not found in selected season")
    return result[0]


def project_event(db, row):
    count = rows(
        db,
        "SELECT count(*) AS n FROM forecast_publications WHERE race_id = :id",
        id=row["id"],
    )[0]["n"]
    return Event(
        id=row["id"],
        event_key=row["event_key"],
        season=row["season"],
        round=row["round"],
        name=row["name"],
        date=row["date"],
        lifecycle="completed" if row["is_completed"] else row["lifecycle_status"],
        circuit_name=display_alias(db, "circuit", row["circuit_key"], row["date"]),
        coverage=Coverage(
            state="complete" if count == 2 else "partial" if count else "empty",
            available=count,
            expected=2,
        ),
    )


def events(db, season):
    require_season(db, season)
    return [project_event(db, row) for row in event_rows(db, season)]


def sessions(db, season, event_id):
    require_event(db, season, event_id)
    return [
        EventSession(**row)
        for row in rows(
            db,
            """SELECT s.id, s.kind, s.scheduled_at, s.revision, s.status
        FROM event_sessions s
        WHERE s.race_id = :id AND s.revision = (
            SELECT max(t.revision) FROM event_sessions t
            WHERE t.race_id = s.race_id AND t.kind = s.kind
        ) ORDER BY s.scheduled_at, s.kind""",
            id=event_id,
        )
    ]


def _freshness(run):
    cutoff, issued, available = (
        timestamp(run[key])
        for key in ("input_cutoff_at", "issue_at", "source_available_at")
    )
    if not all((cutoff, issued, available)):
        state, reason = "unknown", "Source timing is incomplete"
    elif available > cutoff:
        state, reason = (
            "source_late",
            "Source became available after the recorded cutoff",
        )
    elif run["provenance_grade"] == "verified":
        state, reason = "verified_as_of_cutoff", None
    else:
        state, reason = "unknown", "Observed timing has not been independently verified"
    # Historical snapshots do not become stale merely because wall-clock time passes.
    return Freshness(
        state=state,
        input_cutoff_at=cutoff,
        issued_at=issued,
        source_available_at=available,
        reason=reason,
    )


def _probability(output):
    payload = decoded(output)
    if not isinstance(payload, dict):
        raise PublicReadError("invalid_publication", "Published output is invalid", 503)
    value = payload.get("win_probability")
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise PublicReadError(
            "invalid_publication", "Published probability is invalid", 503
        )
    return float(value)


def project_run(db, event, run):
    if (
        run["provenance_grade"] not in {"verified", "observed"}
        or run["result_revision_id"] is not None
    ):
        raise PublicReadError(
            "invalid_publication",
            "Publication is not eligible for public forecasts",
            503,
        )
    outputs = rows(
        db,
        "SELECT entry_key, output FROM forecast_entry_outputs "
        "WHERE forecast_run_id = :id ORDER BY entry_key",
        id=run["forecast_run_id"],
    )
    if not outputs or len(outputs) != run["expected_entry_count"]:
        raise PublicReadError(
            "invalid_publication", "Published field is incomplete", 503
        )
    entries = {
        f"entry:{row['id']}": row
        for row in rows(
            db,
            """SELECT e.id, d.identity_key AS driver_key, c.identity_key AS team_key
        FROM event_entries e JOIN drivers d ON d.id = e.driver_id
        JOIN constructors c ON c.id = e.constructor_id WHERE e.race_id = :id""",
            id=event["id"],
        )
    }
    public_entries = []
    for output in outputs:
        entry = entries.get(output["entry_key"])
        if entry is None:
            raise PublicReadError(
                "invalid_publication", "Published entry identity is unavailable", 503
            )
        public_entries.append(
            PublicEntry(
                entry_key=output["entry_key"],
                driver_name=display_alias(
                    db, "driver", entry["driver_key"], event["date"]
                ),
                team_name=display_alias(db, "team", entry["team_key"], event["date"]),
                win_probability=_probability(output["output"]),
            )
        )
    known = sum(item.win_probability is not None for item in public_entries)
    return PublishedRun(
        run_id=run["forecast_run_id"],
        season=event["season"],
        event_id=event["id"],
        horizon=run["horizon"],
        published_at=timestamp(run["published_at"]),
        source_name={
            "jolpica": "Jolpica",
            "fastf1": "FastF1",
            "open-meteo": "Open-Meteo",
            "openf1": "OpenF1",
            "fixture": "Synthetic acceptance fixture",
        }.get(run["source_provider"]),
        provenance=run["provenance_grade"],
        freshness=_freshness(run),
        coverage=Coverage(
            state="complete" if known == len(outputs) else "partial",
            available=known,
            expected=len(outputs),
            reason=None
            if known == len(outputs)
            else "Some probabilities are unavailable",
        ),
        entries=public_entries,
    )


def published_runs(db, season, event_id, *, horizon=None, run_id=None):
    event = require_event(db, season, event_id)
    sql = """SELECT f.forecast_run_id, f.horizon, f.input_cutoff_at, f.issue_at,
    f.source_available_at, f.provenance_grade, f.expected_entry_count,
    f.result_revision_id, p.published_at, s.provider AS source_provider
    FROM forecast_publications p
    JOIN forecast_runs f ON f.forecast_run_id = p.forecast_run_id
      AND f.race_id = p.race_id AND f.horizon = p.horizon
    LEFT JOIN raw_provider_snapshots s ON s.snapshot_id = f.raw_snapshot_id
    WHERE p.race_id = :id"""
    if horizon is not None:
        sql += " AND p.horizon = :horizon"
    if run_id is not None:
        sql += " AND p.forecast_run_id = :run_id"
    return [
        project_run(db, event, run)
        for run in rows(
            db, sql + " ORDER BY p.horizon", id=event_id, horizon=horizon, run_id=run_id
        )
    ]


def selection(db, season, event_id, horizon):
    runs = published_runs(db, season, event_id, horizon=horizon)
    return PublishedForecast(run=runs[0]) if runs else UnavailableForecast()
