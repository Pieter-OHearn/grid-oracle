"""Unit tests for pipeline.ingest.upsert_helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from pipeline.ingest.upsert_helpers import (
    upsert_circuit,
    upsert_circuit_from_event,
    upsert_constructor,
    upsert_driver,
    upsert_driver_contract,
    upsert_race,
)


def _conn(returning_id=1):
    """Return a mock connection whose execute().fetchone() yields (returning_id,)."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (returning_id,)
    conn.execute.return_value.scalar_one.return_value = returning_id
    return conn


def _session(name="Bahrain Grand Prix", country="Bahrain", city="Sakhir"):
    session = MagicMock()
    session.event.__getitem__.side_effect = {
        "EventName": name,
        "Country": country,
        "Location": city,
    }.__getitem__
    return session


# ---------------------------------------------------------------------------
# upsert_circuit
# ---------------------------------------------------------------------------


def test_upsert_circuit_returns_id_on_insert():
    conn = _conn(returning_id=5)
    result = upsert_circuit(conn, _session())
    assert result == 5


def test_upsert_circuit_falls_back_to_select_on_conflict():
    conn = MagicMock()
    # INSERT returns nothing (DO NOTHING), SELECT returns id
    conn.execute.return_value.fetchone.return_value = None
    conn.execute.return_value.scalar_one.return_value = 3
    result = upsert_circuit(conn, _session())
    assert result == 3


# ---------------------------------------------------------------------------
# upsert_circuit_from_event
# ---------------------------------------------------------------------------


def test_upsert_circuit_from_event_returns_id_on_insert():
    conn = _conn(returning_id=5)
    result = upsert_circuit_from_event(conn, "Bahrain Grand Prix", "Bahrain", "Sakhir")
    assert result == 5


def test_upsert_circuit_from_event_falls_back_to_select():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    conn.execute.return_value.scalar_one.return_value = 3
    result = upsert_circuit_from_event(conn, "Bahrain Grand Prix", "Bahrain", "Sakhir")
    assert result == 3


# ---------------------------------------------------------------------------
# upsert_driver
# ---------------------------------------------------------------------------


def test_upsert_driver_returns_id_on_insert():
    conn = _conn(returning_id=7)
    assert upsert_driver(conn, "VER", "Max Verstappen", "NED") == 7


def test_upsert_driver_falls_back_to_select():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    conn.execute.return_value.scalar_one.return_value = 7
    assert upsert_driver(conn, "VER", "Max Verstappen", "NED") == 7


def test_upsert_driver_passes_correct_params():
    conn = _conn(returning_id=1)
    upsert_driver(conn, "HAM", "Lewis Hamilton", "GBR", 44)
    _, _kwargs = conn.execute.call_args
    # params are passed as the second positional arg
    params = conn.execute.call_args[0][1]
    assert params["code"] == "HAM"
    assert params["full_name"] == "Lewis Hamilton"
    assert params["nationality"] == "GBR"
    assert params["number"] == 44


def test_upsert_driver_number_defaults_to_none():
    conn = _conn(returning_id=1)
    upsert_driver(conn, "HAM", "Lewis Hamilton", "GBR")
    params = conn.execute.call_args[0][1]
    assert params["number"] is None


# ---------------------------------------------------------------------------
# upsert_constructor
# ---------------------------------------------------------------------------


def test_upsert_constructor_returns_id_on_insert():
    conn = _conn(returning_id=2)
    assert upsert_constructor(conn, "Red Bull Racing", "AUT") == 2


def test_upsert_constructor_falls_back_to_select():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    conn.execute.return_value.scalar_one.return_value = 2
    assert upsert_constructor(conn, "Red Bull Racing", "AUT") == 2


# ---------------------------------------------------------------------------
# upsert_race
# ---------------------------------------------------------------------------


def test_upsert_race_mark_completed_true():
    conn = _conn(returning_id=10)
    result = upsert_race(conn, 2023, 1, "Bahrain Grand Prix", 1, "2023-03-05", mark_completed=True)
    assert result == 10
    sql = conn.execute.call_args[0][0].text
    assert "is_completed = TRUE" in sql


def test_upsert_race_mark_completed_false_does_not_set_completed():
    conn = _conn(returning_id=10)
    upsert_race(conn, 2023, 1, "Bahrain Grand Prix", 1, "2023-03-05", mark_completed=False)
    sql = conn.execute.call_args[0][0].text
    assert "is_completed = TRUE" not in sql


def test_upsert_race_falls_back_to_select():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    conn.execute.return_value.scalar_one.return_value = 10
    result = upsert_race(conn, 2023, 1, "Bahrain Grand Prix", 1, "2023-03-05")
    assert result == 10


# ---------------------------------------------------------------------------
# upsert_driver_contract
# ---------------------------------------------------------------------------


def test_upsert_driver_contract_inserts_segment_when_missing():
    conn = MagicMock()
    result_covering = MagicMock()
    result_covering.fetchone.return_value = None
    result_next = MagicMock()
    result_next.fetchone.return_value = None
    conn.execute.side_effect = [result_covering, result_next, MagicMock()]

    upsert_driver_contract(conn, driver_id=1, constructor_id=2, season=2023, round_num=5)

    # Third execute call inserts the new segment
    insert_params = conn.execute.call_args_list[2][0][1]
    assert insert_params["driver_id"] == 1
    assert insert_params["constructor_id"] == 2
    assert insert_params["season"] == 2023
    assert insert_params["start_round"] == 5
    assert insert_params["end_round"] is None


def test_upsert_driver_contract_updates_existing_segment_when_same_round_changes():
    conn = MagicMock()
    current_row = SimpleNamespace(id=7, constructor_id=3, start_round=8, end_round=None)
    result_covering = MagicMock()
    result_covering.fetchone.return_value = current_row
    conn.execute.side_effect = [result_covering, MagicMock()]

    upsert_driver_contract(conn, driver_id=1, constructor_id=4, season=2024, round_num=8)

    # Second execute updates constructor_id on same segment instead of inserting a duplicate
    update_call = conn.execute.call_args_list[1]
    params = update_call[0][1]
    assert params == {"constructor_id": 4, "id": 7}


def test_upsert_driver_contract_closes_previous_segment_and_inserts_new_when_switching():
    conn = MagicMock()
    current_row = SimpleNamespace(id=10, constructor_id=5, start_round=1, end_round=None)
    result_covering = MagicMock()
    result_covering.fetchone.return_value = current_row
    result_next = MagicMock()
    result_next.fetchone.return_value = None
    conn.execute.side_effect = [
        result_covering,  # covering select
        MagicMock(),  # update end_round
        result_next,  # next segment select
        MagicMock(),  # insert new segment
    ]

    upsert_driver_contract(conn, driver_id=2, constructor_id=6, season=2025, round_num=4)

    # update call sets end_round to previous round
    update_params = conn.execute.call_args_list[1][0][1]
    assert update_params["end_round"] == 3
    assert update_params["id"] == 10
    # insert call starts new segment at round 4
    insert_params = conn.execute.call_args_list[3][0][1]
    assert insert_params["start_round"] == 4
