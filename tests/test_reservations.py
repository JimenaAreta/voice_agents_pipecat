import pytest
from pipecat.flows.types import TRANSITION_IN_YAML

from flows.reservations import (
    ReservationSystem,
    check_reservation_availability,
    collect_party_size,
    confirm_reservation,
    normalize_reservation_time,
    start_table_reservation,
)


@pytest.fixture(autouse=True)
def isolated_reservation_database(tmp_path, monkeypatch):
    monkeypatch.setenv("RESERVATIONS_DB_PATH", str(tmp_path / "reservations.sqlite3"))


class FakeFlowManager:
    def __init__(self):
        self.state = {}


def test_time_normalization():
    assert normalize_reservation_time("siete de la tarde") == "19:00"
    assert normalize_reservation_time("17:30") is None


@pytest.mark.asyncio
async def test_database_availability_branches():
    system = ReservationSystem()
    assert await system.check_availability(4, "mañana", "19:00") == (True, [])
    available, alternatives = await system.check_availability(4, "mañana", "20:00")
    assert available is False
    assert alternatives == ["18:00", "19:00", "22:00"]


@pytest.mark.asyncio
async def test_reservation_requires_date_before_party_size():
    result, transition = await collect_party_size(FakeFlowManager(), 4)
    assert result["status"] == "falta_dia"
    assert transition is TRANSITION_IN_YAML


@pytest.mark.asyncio
async def test_available_reservation_requires_valid_contact():
    flow = FakeFlowManager()
    flow.state.update(
        reservation_date="mañana",
        reservation_party_size=4,
        reservation_time="19:00",
    )
    result, transition = await confirm_reservation(flow, "Ana", "123")
    assert result["status"] == "faltan_datos_contacto"
    assert transition is TRANSITION_IN_YAML


@pytest.mark.asyncio
async def test_unavailable_time_offers_alternatives():
    flow = FakeFlowManager()
    flow.state.update(reservation_date="mañana", reservation_party_size=4)
    result, transition = await check_reservation_availability(flow, "20:00")
    assert result["status"] == "no_disponible"
    assert result["available"] is False
    assert result["alternative_times"] == ["18:00", "19:00", "22:00"]
    assert transition is TRANSITION_IN_YAML


@pytest.mark.asyncio
async def test_complete_initial_request_reaches_contact_details():
    flow = FakeFlowManager()
    result, transition = await start_table_reservation(flow, "mañana", 4, "19:00")
    assert result["status"] == "disponible"
    assert result["available"] is True
    assert flow.state["reservation_time"] == "19:00"
    assert transition is TRANSITION_IN_YAML


@pytest.mark.asyncio
async def test_confirmation_is_persisted_and_retry_does_not_duplicate(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "reservations.sqlite3"
    monkeypatch.setenv("RESERVATIONS_DB_PATH", str(path))
    flow = FakeFlowManager()
    flow.state.update(
        reservation_date="12/10", reservation_party_size=4, reservation_time="19:00"
    )
    for _ in range(2):
        result, _ = await confirm_reservation(flow, "Ana", "612345678")
        assert result["status"] == "reserva_confirmada"
        assert result["reservation_date_spoken"] == "el doce de octubre"
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT reservation_date, party_size, customer_name, phone_number FROM reservations"
        ).fetchall() == [("12/10", 4, "Ana", "612345678")]


@pytest.mark.asyncio
async def test_failed_save_never_confirms_reservation(tmp_path, monkeypatch):
    # Una carpeta en la ruta de la base de datos fuerza un error real de SQLite.
    monkeypatch.setenv("RESERVATIONS_DB_PATH", str(tmp_path))
    flow = FakeFlowManager()
    flow.state.update(
        reservation_date="mañana", reservation_party_size=2, reservation_time="19:00"
    )
    result, transition = await confirm_reservation(flow, "Ana", "612345678")
    assert result["status"] == "error_guardado"
    assert transition is TRANSITION_IN_YAML


@pytest.mark.asyncio
async def test_relative_day_is_resolved_before_availability_and_persisted(tmp_path, monkeypatch):
    from datetime import date
    import sqlite3
    from services import validation

    monkeypatch.setattr(validation, "restaurant_today", lambda: date(2026, 10, 18))
    path = tmp_path / "relative.sqlite3"
    monkeypatch.setenv("RESERVATIONS_DB_PATH", str(path))
    flow = FakeFlowManager()
    result, _ = await start_table_reservation(flow, "pasado", 4, "19:00")
    assert result["reservation_date"] == "2026-10-20"
    assert result["reservation_date_spoken"] == "el veinte de octubre de 2026"
    result, _ = await confirm_reservation(flow, "Ana", "612345678")
    assert result["status"] == "reserva_confirmada"
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT reservation_date FROM reservations").fetchone() == ("2026-10-20",)


@pytest.mark.asyncio
async def test_second_call_cannot_book_same_date_and_time(monkeypatch):
    from datetime import date
    from services import validation
    from services.reservation_store import available_times

    monkeypatch.setattr(validation, "restaurant_today", lambda: date(2026, 10, 18))
    first = FakeFlowManager()
    await start_table_reservation(first, "mañana", 4, "19:00")
    result, _ = await confirm_reservation(first, "Ana", "612345678")
    assert result["status"] == "reserva_confirmada"
    # Una llamada nueva y una instancia nueva consultan la misma base de datos.
    second = FakeFlowManager()
    result, _ = await start_table_reservation(second, "mañana", 2, "19:00")
    assert result["status"] == "no_disponible"
    assert result["alternative_times"] == ["18:00", "22:00"]
    assert await ReservationSystem().check_availability(2, "2026-10-19", "19:00") == (
        False, ["18:00", "22:00"]
    )
    assert "19:00" in available_times("2026-10-20")


@pytest.mark.asyncio
async def test_simultaneous_confirmations_only_save_one_booking():
    import asyncio

    flows = [FakeFlowManager(), FakeFlowManager()]
    for flow in flows:
        result, _ = await start_table_reservation(flow, "2026-10-19", 2, "19:00")
        assert result["status"] == "disponible"
    results = await asyncio.gather(*(
        confirm_reservation(flow, "Ana", "612345678") for flow in flows
    ))
    assert sorted(result["status"] for result, _ in results) == [
        "no_disponible", "reserva_confirmada"
    ]
    failed = next(result for result, _ in results if result["status"] == "no_disponible")
    assert failed["alternative_times"] == ["18:00", "22:00"]


@pytest.mark.asyncio
async def test_full_day_has_no_alternatives():
    for time in ["18:00", "19:00", "22:00"]:
        flow = FakeFlowManager()
        await start_table_reservation(flow, "2026-10-19", 2, time)
        result, _ = await confirm_reservation(flow, "Ana", "612345678")
        assert result["status"] == "reserva_confirmada"
    result, _ = await start_table_reservation(FakeFlowManager(), "2026-10-19", 2, "19:00")
    assert result["status"] == "no_disponible"
    assert result["alternative_times"] == []


@pytest.mark.asyncio
async def test_database_read_failure_does_not_claim_availability(tmp_path, monkeypatch):
    monkeypatch.setenv("RESERVATIONS_DB_PATH", str(tmp_path))
    result, _ = await start_table_reservation(FakeFlowManager(), "2026-10-19", 2, "19:00")
    assert result["status"] == "error_disponibilidad"
    assert result["available"] is False


def test_month_calendar_has_all_days_and_varied_availability():
    import sqlite3
    import os
    from services.reservation_store import initialize_calendar, available_times

    initialize_calendar(2026, 10)
    with sqlite3.connect(os.environ["RESERVATIONS_DB_PATH"]) as connection:
        assert connection.execute("SELECT count(*) FROM reservation_calendar").fetchone()[0] == 31 * 5
    assert available_times("2026-10-21") == ["18:00", "19:00", "20:00", "21:00", "22:00"]
    assert available_times("2026-10-22") == []
    assert available_times("2026-10-23") == ["18:00", "20:00", "22:00"]


def test_calendar_initialization_preserves_edits_and_existing_bookings():
    import sqlite3
    import os
    from services.reservation_store import initialize_calendar, save_reservation, available_times

    initialize_calendar(2026, 10)
    save_reservation("existing", dict(reservation_date="2026-10-21", reservation_time="20:00",
                                    party_size=2, customer_name="Ana", phone_number="612345678"))
    with sqlite3.connect(os.environ["RESERVATIONS_DB_PATH"]) as connection:
        connection.execute("UPDATE reservation_calendar SET enabled = 0 WHERE date = '2026-10-21' AND time = '18:00'")
    initialize_calendar(2026, 10)
    assert available_times("2026-10-21") == ["19:00", "21:00", "22:00"]


@pytest.mark.asyncio
async def test_calendar_full_slot_cannot_be_confirmed():
    flow = FakeFlowManager()
    flow.state.update(reservation_date="2026-10-22", reservation_party_size=2, reservation_time="19:00")
    result, _ = await confirm_reservation(flow, "Ana", "612345678")
    assert result["status"] == "no_disponible"
    assert result["alternative_times"] == []
