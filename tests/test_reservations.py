import pytest
from pipecat.flows.types import TRANSITION_IN_YAML

from flows.reservations import (
    MockReservationSystem,
    check_reservation_availability,
    collect_party_size,
    confirm_reservation,
    normalize_reservation_time,
    start_table_reservation,
)


class FakeFlowManager:
    def __init__(self):
        self.state = {}


def test_time_normalization():
    assert normalize_reservation_time("siete de la tarde") == "19:00"
    assert normalize_reservation_time("17:30") is None


@pytest.mark.asyncio
async def test_mock_availability_branches():
    system = MockReservationSystem()
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
