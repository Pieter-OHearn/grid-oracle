"""Season domain kept from live provider payloads: events, sessions, the field.

Identities are provider-scoped (`provider:jolpica:<kind>:<id>`), exactly as the
WP05 dataset names them, and display names are dated aliases. Sessions and
entries are revisioned, never rewritten: a moved session appends a revision,
and a driver change closes one entry and opens another.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Any

from gridoracle.ops.bundle import canonical
from sqlalchemy import text

from pipeline.orchestration import EventSchedule, JobBlocked

CONTRACT_VERSION = "2026.1"
PROVIDER = "jolpica"
DISPLAY = "display"

# Provider schedule key, stored session kind, orchestration session name.
SESSIONS = (
    ("FirstPractice", "practice_1", "Practice 1"),
    ("SecondPractice", "practice_2", "Practice 2"),
    ("ThirdPractice", "practice_3", "Practice 3"),
    ("SprintQualifying", "sprint_qualifying", "Sprint Qualifying"),
    ("SprintShootout", "sprint_qualifying", "Sprint Qualifying"),
    ("Sprint", "sprint", "Sprint"),
    ("Qualifying", "qualifying", "Qualifying"),
)
RACE = ("race", "Race")
NAMES = {kind: name for _, kind, name in SESSIONS} | {RACE[0]: RACE[1]}

TEAM_COLORS = {
    "red_bull": "#3671C6",
    "ferrari": "#E8002D",
    "mercedes": "#27F4D2",
    "mclaren": "#FF8000",
    "aston_martin": "#229971",
    "alpine": "#FF87BC",
    "williams": "#64C4FF",
    "rb": "#6692FF",
    "haas": "#B6BABD",
    "audi": "#52E252",
    "sauber": "#52E252",
    "cadillac": "#CC0000",
}
UNKNOWN_COLOR = "#000000"


def identity(kind: str, provider_id: str) -> str:
    return f"provider:{PROVIDER}:{kind}:{provider_id}"


def provider_id(identity_key: str) -> str | None:
    prefix, _, value = identity_key.rpartition(":")
    return value if prefix.startswith(f"provider:{PROVIDER}:") else None


def moment(block: Mapping[str, Any]) -> datetime | None:
    if not block.get("date") or not block.get("time"):
        return None
    value = f"{block['date']}T{block['time']}".replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(UTC)


def positive_int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


@dataclass(frozen=True)
class CalendarEvent:
    season: int
    round_number: int
    name: str
    circuit: Mapping[str, Any]
    date: date
    sessions: Mapping[str, datetime]  # stored kind -> start

    @property
    def race_start(self) -> datetime:
        return self.sessions[RACE[0]]


def parse_schedule(races: Iterable[Mapping[str, Any]]) -> list[CalendarEvent]:
    events = []
    for race in races:
        sessions = {}
        for key, kind, _ in SESSIONS:
            if key in race and (at := moment(race[key])) is not None:
                sessions[kind] = at
        race_at = moment(race)
        if race_at is None:
            # A race without a published start time cannot be scheduled.
            continue
        sessions[RACE[0]] = race_at
        events.append(
            CalendarEvent(
                season=int(race["season"]),
                round_number=int(race["round"]),
                name=str(race["raceName"]),
                circuit=race["Circuit"],
                date=date.fromisoformat(race["date"]),
                sessions=sessions,
            )
        )
    return events


def _alias(conn, kind: str, key: str, provider: str, value: str, *, display: bool):
    taken = conn.execute(
        text(
            "SELECT identity_key FROM entity_aliases WHERE entity_kind=:kind "
            "AND provider=:provider AND provider_key=:value"
        ),
        {"kind": kind, "provider": provider, "value": value},
    ).fetchall()
    if taken:
        # One alias per provider key; a clash with another identity is left
        # unresolved (the public API then shows no name, never a wrong one).
        return
    conn.execute(
        text(
            "INSERT INTO entity_aliases (entity_kind, identity_key, provider, "
            "provider_key, valid_from, valid_to, is_display_alias) "
            "VALUES (:kind, :key, :provider, :value, NULL, NULL, :display)"
        ),
        {
            "kind": kind,
            "key": key,
            "provider": provider,
            "value": value,
            "display": display,
        },
    )


def _id_for(conn, table: str, key: str) -> int | None:
    return conn.execute(text(f"SELECT id FROM {table} WHERE identity_key=:key"), {"key": key}).scalar_one_or_none()


def ensure_ruleset(conn, season: int) -> None:
    exists = conn.execute(
        text("SELECT 1 FROM season_rulesets WHERE season=:season AND ruleset_version=:version"),
        {"season": season, "version": CONTRACT_VERSION},
    ).fetchone()
    if exists is None:
        conn.execute(
            text(
                "INSERT INTO season_rulesets (season, ruleset_version, source, "
                "is_current, payload) VALUES (:season, :version, :source, true, "
                ":payload)"
            ),
            {
                "season": season,
                "version": CONTRACT_VERSION,
                "source": "gridoracle season and target contract",
                "payload": canonical({"contract": "docs/domain/SEASON_AND_TARGET_CONTRACT.md"}).decode(),
            },
        )


def ensure_circuit(conn, circuit: Mapping[str, Any]) -> int:
    key = identity("circuit", str(circuit["circuitId"]))
    found = _id_for(conn, "circuits", key)
    if found is None:
        location = circuit.get("Location", {})
        found = conn.execute(
            text(
                "INSERT INTO circuits (name, country, city, circuit_type, "
                "total_laps, length_km, identity_key) VALUES (:name, :country, "
                ":city, 'unknown', 0, 0, :key) RETURNING id"
            ),
            {
                "name": str(circuit["circuitName"]),
                "country": str(location.get("country", "")),
                "city": str(location.get("locality", "")),
                "key": key,
            },
        ).scalar_one()
    _alias(conn, "circuit", key, PROVIDER, str(circuit["circuitId"]), display=False)
    _alias(conn, "circuit", key, DISPLAY, str(circuit["circuitName"]), display=True)
    return int(found)


def ensure_driver(conn, driver: Mapping[str, Any]) -> int:
    provider_key = str(driver["driverId"])
    key = identity("driver", provider_key)
    found = _id_for(conn, "drivers", key)
    name = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
    if found is None:
        code = str(driver.get("code") or provider_key[:3]).upper()[:3]
        clash = conn.execute(
            text("SELECT identity_key FROM drivers WHERE code=:code"), {"code": code}
        ).scalar_one_or_none()
        if clash is not None:
            raise JobBlocked(f"driver code {code} already belongs to {clash}; curate an alias")
        found = conn.execute(
            text(
                "INSERT INTO drivers (code, full_name, nationality, number, "
                "identity_key) VALUES (:code, :name, :nationality, :number, :key) "
                "RETURNING id"
            ),
            {
                "code": code,
                "name": name or provider_key,
                "nationality": str(driver.get("nationality", "")),
                "number": positive_int(driver.get("permanentNumber")),
                "key": key,
            },
        ).scalar_one()
    _alias(conn, "driver", key, PROVIDER, provider_key, display=False)
    if name:
        _alias(conn, "driver", key, DISPLAY, name, display=True)
    return int(found)


def ensure_constructor(conn, constructor: Mapping[str, Any]) -> int:
    provider_key = str(constructor["constructorId"])
    key = identity("team", provider_key)
    found = _id_for(conn, "constructors", key)
    name = str(constructor.get("name") or provider_key)
    if found is None:
        found = conn.execute(
            text(
                "INSERT INTO constructors (name, nationality, color_hex, "
                "identity_key) VALUES (:name, :nationality, :color, :key) "
                "RETURNING id"
            ),
            {
                "name": name,
                "nationality": str(constructor.get("nationality", "")),
                "color": TEAM_COLORS.get(provider_key, UNKNOWN_COLOR),
                "key": key,
            },
        ).scalar_one()
    _alias(conn, "team", key, PROVIDER, provider_key, display=False)
    _alias(conn, "team", key, DISPLAY, name, display=True)
    return int(found)


def sync_calendar(conn, events: Iterable[CalendarEvent]) -> dict[int, int]:
    """Upsert events and append session revisions. Returns round -> race id."""
    races: dict[int, int] = {}
    for event in events:
        ensure_ruleset(conn, event.season)
        circuit_id = ensure_circuit(conn, event.circuit)
        race_id = conn.execute(
            text("SELECT id FROM races WHERE season=:season AND round=:round"),
            {"season": event.season, "round": event.round_number},
        ).scalar_one_or_none()
        if race_id is None:
            race_id = conn.execute(
                text(
                    "INSERT INTO races (season, round, name, circuit_id, date, "
                    "is_completed) VALUES (:season, :round, :name, :circuit, :date, "
                    "false) RETURNING id"
                ),
                {
                    "season": event.season,
                    "round": event.round_number,
                    "name": event.name,
                    "circuit": circuit_id,
                    "date": event.date,
                },
            ).scalar_one()
        else:
            conn.execute(
                text("UPDATE races SET name=:name, circuit_id=:circuit, date=:date WHERE id=:id"),
                {
                    "name": event.name,
                    "circuit": circuit_id,
                    "date": event.date,
                    "id": race_id,
                },
            )
        moved = False
        for kind, at in event.sessions.items():
            latest = conn.execute(
                text(
                    "SELECT revision, scheduled_at FROM event_sessions "
                    "WHERE race_id=:race AND kind=:kind "
                    "ORDER BY revision DESC LIMIT 1"
                ),
                {"race": race_id, "kind": kind},
            ).fetchone()
            if latest is not None and _same_instant(latest.scheduled_at, at):
                continue
            moved = moved or latest is not None
            conn.execute(
                text(
                    "INSERT INTO event_sessions (race_id, kind, scheduled_at, "
                    "revision, status) VALUES (:race, :kind, :at, :revision, "
                    "'scheduled')"
                ),
                {
                    "race": race_id,
                    "kind": kind,
                    "at": at,
                    "revision": 1 if latest is None else latest.revision + 1,
                },
            )
        if moved:
            conn.execute(
                text("UPDATE races SET schedule_revision = schedule_revision + 1 WHERE id=:id"),
                {"id": race_id},
            )
        races[event.round_number] = int(race_id)
    return races


def _same_instant(stored: Any, desired: datetime) -> bool:
    if isinstance(stored, str):
        stored = datetime.fromisoformat(stored)
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=UTC)
    return stored.astimezone(UTC) == desired.astimezone(UTC)


def sessions(conn, race_id: int) -> dict[str, datetime]:
    """The latest revision of each session, keyed by orchestration name."""
    rows = conn.execute(
        text(
            "SELECT s.kind, s.scheduled_at FROM event_sessions s WHERE "
            "s.race_id=:race AND s.revision = (SELECT max(t.revision) FROM "
            "event_sessions t WHERE t.race_id=s.race_id AND t.kind=s.kind)"
        ),
        {"race": race_id},
    ).fetchall()
    result = {}
    for kind, at in rows:
        if isinstance(at, str):
            at = datetime.fromisoformat(at)
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        result[NAMES.get(kind, kind)] = at.astimezone(UTC)
    return result


def initial_field_size(conn, race_id: int) -> int:
    """Entries that open the field; transfers replace one and add none."""
    return int(
        conn.execute(
            text("SELECT count(*) FROM event_entries WHERE race_id=:race AND replaces_entry_id IS NULL"),
            {"race": race_id},
        ).scalar_one()
    )


def schedule(conn, race_id: int) -> EventSchedule:
    race = conn.execute(
        text("SELECT season, round, lifecycle_status FROM races WHERE id=:id"),
        {"id": race_id},
    ).one()
    return EventSchedule(
        race_id=race_id,
        season=int(race.season),
        round_number=int(race.round),
        sessions=sessions(conn, race_id),
        expected_entries=initial_field_size(conn, race_id),
        lifecycle=str(race.lifecycle_status),
    )


@dataclass(frozen=True)
class Entry:
    id: int
    driver_id: int
    constructor_id: int
    driver_key: str
    team_key: str

    @property
    def key(self) -> str:
        return f"entry:{self.id}"


def field(conn, race_id: int) -> list[Entry]:
    rows = conn.execute(
        text(
            "SELECT e.id, e.driver_id, e.constructor_id, d.identity_key AS dk, "
            "c.identity_key AS tk FROM event_entries e "
            "JOIN drivers d ON d.id = e.driver_id "
            "JOIN constructors c ON c.id = e.constructor_id "
            "WHERE e.race_id=:race AND e.status='active' ORDER BY e.id"
        ),
        {"race": race_id},
    ).fetchall()
    return [Entry(r.id, r.driver_id, r.constructor_id, r.dk, r.tk) for r in rows]


def previous_round(conn, race_id: int):
    """The round just before this event in its season, completed or not."""
    return conn.execute(
        text(
            "SELECT p.id, p.is_completed FROM races r JOIN races p ON "
            "p.season = r.season AND p.round < r.round WHERE r.id=:id "
            "ORDER BY p.round DESC LIMIT 1"
        ),
        {"id": race_id},
    ).one_or_none()


def carry_forward_field(conn, race_id: int) -> int:
    """Open the field once, from the round before's classified entrants.

    An event further ahead stays closed until the round just before it has a
    classification, so every event opens from its own predecessor.
    """
    existing = conn.execute(
        text("SELECT count(*) FROM event_entries WHERE race_id=:race"),
        {"race": race_id},
    ).scalar_one()
    if existing:
        return initial_field_size(conn, race_id)
    before = previous_round(conn, race_id)
    if before is None:
        raise JobBlocked("the season's first event needs a curated entry list")
    if not before.is_completed:
        raise JobBlocked("the round before has no classification yet")
    previous = before.id
    rows = conn.execute(
        text("SELECT driver_id, constructor_id FROM race_results WHERE race_id=:race ORDER BY driver_id"),
        {"race": previous},
    ).fetchall()
    if not rows:
        raise JobBlocked("the previous round has no stored classification")
    for row in rows:
        conn.execute(
            text(
                "INSERT INTO event_entries (race_id, driver_id, constructor_id, "
                "role, status, revision) VALUES (:race, :driver, :team, "
                "'primary', 'active', 1)"
            ),
            {"race": race_id, "driver": row.driver_id, "team": row.constructor_id},
        )
    return len(rows)


def revise_field(conn, race_id: int, entrants: Iterable[tuple[int, int]]) -> int:
    """Make the active field the qualifying entrants: (driver, constructor)."""
    wanted = dict(entrants)
    active = {entry.driver_id: entry for entry in field(conn, race_id)}
    vacated = {driver: entry for driver, entry in active.items() if driver not in wanted}
    for driver, team in wanted.items():
        current = active.get(driver)
        if current is not None and current.constructor_id == team:
            continue
        replaced = current or next((e for e in vacated.values() if e.constructor_id == team), None)
        if replaced is not None:
            conn.execute(
                text("UPDATE event_entries SET status='withdrawn' WHERE id=:id"),
                {"id": replaced.id},
            )
            vacated.pop(replaced.driver_id, None)
        revision = conn.execute(
            text("SELECT coalesce(max(revision), 0) + 1 FROM event_entries WHERE race_id=:race AND driver_id=:driver"),
            {"race": race_id, "driver": driver},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO event_entries (race_id, driver_id, constructor_id, "
                "role, status, revision, replaces_entry_id) VALUES (:race, "
                ":driver, :team, 'primary', 'active', :revision, :replaces)"
            ),
            {
                "race": race_id,
                "driver": driver,
                "team": team,
                "revision": revision,
                "replaces": None if replaced is None else replaced.id,
            },
        )
    for entry in vacated.values():
        conn.execute(
            text("UPDATE event_entries SET status='withdrawn' WHERE id=:id"),
            {"id": entry.id},
        )
    return len(field(conn, race_id))


def _lap_seconds(value: object) -> str | None:
    """Jolpica lap time `M:SS.mmm` as a PostgreSQL interval literal."""
    if not value:
        return None
    minutes, _, seconds = str(value).rpartition(":")
    try:
        total = (int(minutes) * 60 if minutes else 0) + float(seconds)
    except ValueError:
        return None
    return f"{total} seconds"


def record_qualifying(conn, race_id: int, race: Mapping[str, Any]) -> list[tuple]:
    """Store the Grand Prix qualifying classification; return entrants."""
    entrants = []
    for row in race.get("QualifyingResults", []):
        driver = ensure_driver(conn, row["Driver"])
        team = ensure_constructor(conn, row["Constructor"])
        position = positive_int(row.get("position"))
        conn.execute(
            text(
                "INSERT INTO qualifying_results (race_id, driver_id, constructor_id, "
                "q1_time, q2_time, q3_time, grid_position) VALUES (:race, :driver, "
                ":team, CAST(:q1 AS interval), CAST(:q2 AS interval), "
                "CAST(:q3 AS interval), :position) ON CONFLICT (race_id, driver_id) "
                "DO UPDATE SET constructor_id=EXCLUDED.constructor_id, "
                "q1_time=EXCLUDED.q1_time, q2_time=EXCLUDED.q2_time, "
                "q3_time=EXCLUDED.q3_time, grid_position=EXCLUDED.grid_position"
            ),
            {
                "race": race_id,
                "driver": driver,
                "team": team,
                "q1": _lap_seconds(row.get("Q1")),
                "q2": _lap_seconds(row.get("Q2")),
                "q3": _lap_seconds(row.get("Q3")),
                "position": position,
            },
        )
        entrants.append((driver, team, position))
    return entrants


def classification_digest(rows: Iterable[Mapping[str, Any]]) -> str:
    material = sorted(
        (
            str(row["Driver"]["driverId"]),
            str(row["Constructor"]["constructorId"]),
            str(row.get("positionText")),
            str(row.get("status")),
            str(row.get("points")),
            str(row.get("grid")),
        )
        for row in rows
    )
    return sha256(canonical(material)).hexdigest()


def record_results(conn, race_id: int, race: Mapping[str, Any], *, recorded_at: datetime) -> int:
    """Store the classification; append a result revision when it changed."""
    rows = race.get("Results", [])
    for row in rows:
        driver = ensure_driver(conn, row["Driver"])
        team = ensure_constructor(conn, row["Constructor"])
        grid = row.get("grid")
        conn.execute(
            text(
                "INSERT INTO race_results (race_id, driver_id, constructor_id, "
                "grid_position, finish_position, points, status, fastest_lap, "
                "is_wet_race) VALUES (:race, :driver, :team, :grid, :finish, "
                ":points, :status, :fastest, false) ON CONFLICT (race_id, "
                "driver_id) DO UPDATE SET constructor_id=EXCLUDED.constructor_id, "
                "grid_position=EXCLUDED.grid_position, "
                "finish_position=EXCLUDED.finish_position, points=EXCLUDED.points, "
                "status=EXCLUDED.status, fastest_lap=EXCLUDED.fastest_lap"
            ),
            {
                "race": race_id,
                "driver": driver,
                "team": team,
                "grid": int(grid) if str(grid or "").isdigit() else None,
                "finish": positive_int(row.get("positionText")),
                "points": float(row.get("points", 0) or 0),
                "status": str(row.get("status", "Unknown")),
                "fastest": str(row.get("FastestLap", {}).get("rank")) == "1",
            },
        )
    conn.execute(
        text("UPDATE races SET is_completed=true, lifecycle_status='completed' WHERE id=:id"),
        {"id": race_id},
    )
    reason = f"jolpica classification sha256:{classification_digest(rows)[:16]}"
    latest = conn.execute(
        text("SELECT id, revision, reason FROM result_revisions WHERE race_id=:race ORDER BY revision DESC LIMIT 1"),
        {"race": race_id},
    ).fetchone()
    if latest is not None and latest.reason == reason:
        return int(latest.id)
    return int(
        conn.execute(
            text(
                "INSERT INTO result_revisions (race_id, revision, source, reason, "
                "is_official, recorded_at) VALUES (:race, :revision, 'jolpica', "
                ":reason, true, :at) RETURNING id"
            ),
            {
                "race": race_id,
                "revision": 1 if latest is None else latest.revision + 1,
                "reason": reason,
                "at": recorded_at,
            },
        ).scalar_one()
    )
