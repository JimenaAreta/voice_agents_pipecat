"""Flujo de reservas de mesa inspirado en `restaurant_reservation.py`.

El ejemplo original de Pipecat Flows comprueba disponibilidad con un sistema
simulado. Aquí mantenemos esa idea, pero en español y dentro de El Rincón de Castilla.
"""

from typing import TypedDict

from loguru import logger
from pipecat_flows import FlowManager, NodeConfig

from services.common_nodes import create_end_node, return_to_main_menu
from services.speech_format import (
    format_phone_for_speech,
    format_time_for_speech,
    format_times_for_speech,
)


class MockReservationSystem:
    """Simula una API de reservas del restaurante."""

    def __init__(self) -> None:
        # Horas que simulamos como completas. El LLM trabajará con formato 24h.
        self.booked_times = {"20:00", "21:00"}

    async def check_availability(
        self, party_size: int, reservation_date: str, requested_time: str
    ) -> tuple[bool, list[str]]:
        """Comprueba si hay mesa disponible para fecha, tamaño y hora solicitados."""
        is_available = requested_time not in self.booked_times
        alternatives: list[str] = []
        if not is_available:
            base_times = ["18:00", "19:00", "20:00", "21:00", "22:00"]
            alternatives = [time for time in base_times if time not in self.booked_times]

        return is_available, alternatives


reservation_system = MockReservationSystem()

VALID_RESERVATION_TIMES = {"18:00", "19:00", "20:00", "21:00", "22:00"}
TIME_ALIASES = {
    "6": "18:00",
    "6:00": "18:00",
    "18": "18:00",
    "18:00": "18:00",
    "seis": "18:00",
    "seis de la tarde": "18:00",
    "7": "19:00",
    "7:00": "19:00",
    "19": "19:00",
    "19:00": "19:00",
    "siete": "19:00",
    "siete de la tarde": "19:00",
    "8": "20:00",
    "8:00": "20:00",
    "20": "20:00",
    "20:00": "20:00",
    "ocho": "20:00",
    "ocho de la tarde": "20:00",
    "9": "21:00",
    "9:00": "21:00",
    "21": "21:00",
    "21:00": "21:00",
    "nueve": "21:00",
    "nueve de la noche": "21:00",
    "10": "22:00",
    "10:00": "22:00",
    "22": "22:00",
    "22:00": "22:00",
    "diez": "22:00",
    "diez de la noche": "22:00",
}


class PartySizeResult(TypedDict):
    """Resultado de recoger el número de comensales."""

    party_size: int
    status: str


class AvailabilityResult(TypedDict):
    """Resultado de comprobar disponibilidad."""

    status: str
    reservation_date: str
    party_size: int
    requested_time: str
    requested_time_spoken: str
    available: bool
    alternative_times: list[str]
    alternative_times_spoken: str


class ReservationStartResult(TypedDict):
    """Resultado de iniciar una reserva desde el primer turno."""

    status: str
    reservation_date: str
    party_size: int
    requested_time: str
    requested_time_spoken: str
    available: bool | None
    alternative_times: list[str]
    alternative_times_spoken: str


class ReservationResult(TypedDict):
    """Resultado final de la reserva."""

    status: str
    reservation_date: str
    party_size: int
    reservation_time: str
    reservation_time_spoken: str
    customer_name: str
    phone_number: str
    phone_spoken: str


def ensure_reservation_state(flow_manager: FlowManager) -> None:
    """Inicializa el estado necesario para una reserva."""
    flow_manager.state.setdefault("reservation_date", None)
    flow_manager.state.setdefault("reservation_party_size", None)
    flow_manager.state.setdefault("reservation_time", None)
    flow_manager.state.setdefault("reservation_name", None)
    flow_manager.state.setdefault("reservation_phone", None)


def normalize_reservation_time(requested_time: str) -> str | None:
    """Normaliza horas habladas o escritas al formato 24h usado por el flujo."""
    clean_time = requested_time.strip().lower()
    return TIME_ALIASES.get(clean_time)


async def start_table_reservation(
    flow_manager: FlowManager,
    reservation_date: str = "",
    party_size: int = 0,
    requested_time: str = "",
) -> tuple[ReservationStartResult, NodeConfig]:
    """
    Empieza una reserva de mesa desde el nodo inicial.

    Args:
        reservation_date: Día de la reserva, por ejemplo hoy, mañana, viernes o 25 de mayo.
        party_size: Número de personas. Debe estar entre 1 y 12.
        requested_time: Hora opcional de la reserva. Puede ser 19:00, 20:00, ocho de la tarde, etc.
    """
    ensure_reservation_state(flow_manager)
    if not reservation_date.strip():
        return {
            "status": "falta_dia",
            "reservation_date": "",
            "party_size": party_size,
            "requested_time": requested_time,
            "requested_time_spoken": format_time_for_speech(requested_time),
            "available": None,
            "alternative_times": [],
            "alternative_times_spoken": "",
        }, create_reservation_date_node()

    flow_manager.state["reservation_date"] = reservation_date.strip()

    if party_size == 0:
        return {
            "status": "falta_personas",
            "reservation_date": flow_manager.state["reservation_date"],
            "party_size": party_size,
            "requested_time": requested_time,
            "requested_time_spoken": format_time_for_speech(requested_time),
            "available": None,
            "alternative_times": [],
            "alternative_times_spoken": "",
        }, create_reservation_party_node()

    if party_size < 1 or party_size > 12:
        return {
            "status": "tamaño_no_valido",
            "reservation_date": flow_manager.state["reservation_date"],
            "party_size": party_size,
            "requested_time": requested_time,
            "requested_time_spoken": format_time_for_speech(requested_time),
            "available": None,
            "alternative_times": [],
            "alternative_times_spoken": "",
        }, create_reservation_party_node()

    flow_manager.state["reservation_party_size"] = party_size

    if not requested_time.strip():
        return {
            "status": "falta_hora",
            "reservation_date": flow_manager.state["reservation_date"],
            "party_size": party_size,
            "requested_time": "",
            "requested_time_spoken": "",
            "available": None,
            "alternative_times": [],
            "alternative_times_spoken": "",
        }, create_reservation_time_node()

    normalized_time = normalize_reservation_time(requested_time)
    if normalized_time is None:
        return {
            "status": "hora_no_valida",
            "reservation_date": flow_manager.state["reservation_date"],
            "party_size": party_size,
            "requested_time": requested_time,
            "requested_time_spoken": format_time_for_speech(requested_time),
            "available": None,
            "alternative_times": sorted(VALID_RESERVATION_TIMES),
            "alternative_times_spoken": format_times_for_speech(sorted(VALID_RESERVATION_TIMES)),
        }, create_reservation_time_node()

    is_available, alternative_times = await reservation_system.check_availability(
        party_size, flow_manager.state["reservation_date"], normalized_time
    )
    flow_manager.state["reservation_time"] = normalized_time if is_available else None

    result: ReservationStartResult = {
        "status": "ok",
        "reservation_date": flow_manager.state["reservation_date"],
        "party_size": party_size,
        "requested_time": normalized_time,
        "requested_time_spoken": format_time_for_speech(normalized_time),
        "available": is_available,
        "alternative_times": alternative_times,
        "alternative_times_spoken": format_times_for_speech(alternative_times),
    }
    if is_available:
        return result, create_reservation_details_node()
    return result, create_no_availability_node(alternative_times)


async def collect_reservation_date(
    flow_manager: FlowManager, reservation_date: str
) -> tuple[dict[str, str], NodeConfig]:
    """
    Registra el día de la reserva.

    Args:
        reservation_date: Día de la reserva, por ejemplo hoy, mañana, viernes o 25 de mayo.
    """
    ensure_reservation_state(flow_manager)
    flow_manager.state["reservation_date"] = reservation_date.strip()
    return {
        "status": "ok",
        "reservation_date": flow_manager.state["reservation_date"],
    }, create_reservation_party_node()


async def collect_party_size(
    flow_manager: FlowManager, party_size: int
) -> tuple[PartySizeResult, NodeConfig]:
    """
    Registra cuántas personas tendrá la reserva.

    Args:
        party_size: Número de personas. Debe estar entre 1 y 12.
    """
    ensure_reservation_state(flow_manager)
    if not flow_manager.state.get("reservation_date"):
        return {
            "party_size": party_size,
            "status": "falta_dia",
        }, create_reservation_date_node()

    if party_size < 1 or party_size > 12:
        return {
            "party_size": party_size,
            "status": "tamaño_no_valido",
        }, create_reservation_party_node()

    flow_manager.state["reservation_party_size"] = party_size
    return {
        "party_size": party_size,
        "status": "ok",
    }, create_reservation_time_node()


async def check_reservation_availability(
    flow_manager: FlowManager, requested_time: str
) -> tuple[AvailabilityResult, NodeConfig]:
    """
    Comprueba si hay mesa disponible para la hora solicitada.

    Args:
        requested_time: Hora de la reserva en formato 24h. Debe ser una de 18:00, 19:00, 20:00, 21:00 o 22:00.
    """
    ensure_reservation_state(flow_manager)
    if not flow_manager.state.get("reservation_date"):
        return {
            "status": "falta_dia",
            "reservation_date": "",
            "party_size": 0,
            "requested_time": requested_time,
            "requested_time_spoken": format_time_for_speech(requested_time),
            "available": False,
            "alternative_times": [],
            "alternative_times_spoken": "",
        }, create_reservation_date_node()

    party_size = flow_manager.state.get("reservation_party_size")
    if not party_size:
        return {
            "status": "falta_personas",
            "reservation_date": flow_manager.state["reservation_date"],
            "party_size": 0,
            "requested_time": requested_time,
            "requested_time_spoken": format_time_for_speech(requested_time),
            "available": False,
            "alternative_times": [],
            "alternative_times_spoken": "",
        }, create_reservation_party_node()

    normalized_time = normalize_reservation_time(requested_time)
    if normalized_time is None:
        return {
            "status": "hora_no_valida",
            "reservation_date": flow_manager.state["reservation_date"],
            "party_size": party_size,
            "requested_time": requested_time,
            "requested_time_spoken": format_time_for_speech(requested_time),
            "available": False,
            "alternative_times": sorted(VALID_RESERVATION_TIMES),
            "alternative_times_spoken": format_times_for_speech(sorted(VALID_RESERVATION_TIMES)),
        }, create_reservation_time_node()

    is_available, alternative_times = await reservation_system.check_availability(
        party_size, flow_manager.state["reservation_date"], normalized_time
    )
    flow_manager.state["reservation_time"] = normalized_time if is_available else None

    result: AvailabilityResult = {
        "status": "ok",
        "reservation_date": flow_manager.state["reservation_date"],
        "party_size": party_size,
        "requested_time": normalized_time,
        "requested_time_spoken": format_time_for_speech(normalized_time),
        "available": is_available,
        "alternative_times": alternative_times,
        "alternative_times_spoken": format_times_for_speech(alternative_times),
    }

    if is_available:
        logger.debug("Hora disponible, pasamos a datos de confirmación.")
        return result, create_reservation_details_node()

    logger.debug(f"Hora no disponible. Alternativas: {alternative_times}")
    return result, create_no_availability_node(alternative_times)


async def confirm_reservation(
    flow_manager: FlowManager, customer_name: str, phone_number: str
) -> tuple[ReservationResult, NodeConfig]:
    """
    Confirma la reserva con nombre y teléfono del cliente.

    Args:
        customer_name: Nombre de la persona que reserva.
        phone_number: Teléfono de contacto para la reserva.
    """
    ensure_reservation_state(flow_manager)
    if not flow_manager.state.get("reservation_date"):
        return {
            "status": "falta_dia",
            "reservation_date": "",
            "party_size": 0,
            "reservation_time": "",
            "reservation_time_spoken": "",
            "customer_name": customer_name.strip(),
            "phone_number": phone_number.strip(),
            "phone_spoken": format_phone_for_speech(phone_number),
        }, create_reservation_date_node()

    if not flow_manager.state.get("reservation_party_size"):
        return {
            "status": "falta_personas",
            "reservation_date": flow_manager.state["reservation_date"],
            "party_size": 0,
            "reservation_time": "",
            "reservation_time_spoken": "",
            "customer_name": customer_name.strip(),
            "phone_number": phone_number.strip(),
            "phone_spoken": format_phone_for_speech(phone_number),
        }, create_reservation_party_node()

    if not flow_manager.state.get("reservation_time"):
        return {
            "status": "falta_hora",
            "reservation_date": flow_manager.state["reservation_date"],
            "party_size": flow_manager.state["reservation_party_size"],
            "reservation_time": "",
            "reservation_time_spoken": "",
            "customer_name": customer_name.strip(),
            "phone_number": phone_number.strip(),
            "phone_spoken": format_phone_for_speech(phone_number),
        }, create_reservation_time_node()

    if not customer_name.strip() or not phone_number.strip():
        return {
            "status": "faltan_datos_contacto",
            "reservation_date": flow_manager.state["reservation_date"],
            "party_size": flow_manager.state["reservation_party_size"],
            "reservation_time": flow_manager.state["reservation_time"],
            "reservation_time_spoken": format_time_for_speech(flow_manager.state["reservation_time"]),
            "customer_name": customer_name.strip(),
            "phone_number": phone_number.strip(),
            "phone_spoken": format_phone_for_speech(phone_number),
        }, create_reservation_details_node()

    flow_manager.state["reservation_name"] = customer_name.strip()
    flow_manager.state["reservation_phone"] = phone_number.strip()

    return {
        "status": "reserva_confirmada",
        "reservation_date": flow_manager.state["reservation_date"],
        "party_size": flow_manager.state["reservation_party_size"],
        "reservation_time": flow_manager.state["reservation_time"],
        "reservation_time_spoken": format_time_for_speech(flow_manager.state["reservation_time"]),
        "customer_name": flow_manager.state["reservation_name"],
        "phone_number": flow_manager.state["reservation_phone"],
        "phone_spoken": format_phone_for_speech(flow_manager.state["reservation_phone"]),
    }, create_end_node()


async def cancel_reservation(flow_manager: FlowManager) -> tuple[None, NodeConfig]:
    """
    Cancela el intento de reserva y termina la conversación.
    """
    return None, create_end_node()


def create_reservation_date_node() -> NodeConfig:
    """Crea el nodo que pregunta el día de la reserva."""
    return NodeConfig(
        name="reservation_date",
        task_messages=[
            {
                "role": "developer",
                "content": (
                    "Ayuda al cliente a reservar una mesa. Pregunta solo el día "
                    "de la reserva. No preguntes todavía personas, hora, nombre ni teléfono. "
                    "Cuando tengas el día, llama a collect_reservation_date. "
                    "Si el cliente quiere pedir comida en vez de reservar, llama a return_to_main_menu."
                ),
            }
        ],
        functions=[collect_reservation_date, return_to_main_menu, cancel_reservation],
    )


def create_reservation_party_node() -> NodeConfig:
    """Crea el nodo que recoge el número de comensales."""
    return NodeConfig(
        name="reservation_party",
        task_messages=[
            {
                "role": "developer",
                "content": (
                    "Ya tienes el día de la reserva. Haz una sola pregunta: "
                    "para cuántas personas será la reserva. No preguntes todavía nombre ni teléfono. "
                    "Si también dice una hora, llama a start_table_reservation con reservation_date, party_size y requested_time. "
                    "Si solo sabes el número de personas, llama a collect_party_size. "
                    "Si el cliente quiere pedir comida en vez de reservar, llama a return_to_main_menu."
                ),
            }
        ],
        functions=[
            start_table_reservation,
            collect_party_size,
            cancel_reservation,
            return_to_main_menu,
        ],
    )


def create_reservation_time_node() -> NodeConfig:
    """Crea el nodo que pide la hora y comprueba disponibilidad."""
    return NodeConfig(
        name="reservation_time",
        task_messages=[
            {
                "role": "developer",
                "content": (
                    "Pregunta a qué hora quiere venir. Haz solo esa pregunta. "
                    "El restaurante acepta reservas "
                    "a las seis de la tarde, siete de la tarde, ocho de la tarde, "
                    "nueve de la noche y diez de la noche. Cuando tengas la hora, "
                    "llama a check_reservation_availability. Acepta también formas habladas "
                    "como ocho de la tarde y normalízalas con la función. Si el cliente quiere "
                    "pedir comida en vez de reservar, llama a return_to_main_menu."
                ),
            }
        ],
        functions=[check_reservation_availability, cancel_reservation, return_to_main_menu],
    )


def create_no_availability_node(alternative_times: list[str]) -> NodeConfig:
    """Crea el nodo que propone horas alternativas cuando no hay disponibilidad."""
    times_list = format_times_for_speech(alternative_times)
    return NodeConfig(
        name="reservation_no_availability",
        task_messages=[
            {
                "role": "developer",
                "content": (
                    f"Disculpa al cliente porque esa hora no está disponible. "
                    f"Ofrece estas alternativas: {times_list}. "
                    "Pregunta cuál prefiere, sin pedir todavía nombre ni teléfono. "
                    "Si acepta una alternativa, llama a check_reservation_availability "
                    "con la nueva hora. Si no quiere reservar, llama a cancel_reservation. "
                    "Si cambia a pedido de comida, llama a return_to_main_menu."
                ),
            }
        ],
        functions=[check_reservation_availability, cancel_reservation, return_to_main_menu],
    )


def create_reservation_details_node() -> NodeConfig:
    """Crea el nodo que recoge datos finales y confirma la reserva."""
    return NodeConfig(
        name="reservation_details",
        task_messages=[
            {
                "role": "developer",
                "content": (
                    "La hora está disponible. Pide primero el nombre del cliente si no lo tienes. "
                    "Después pide siempre el teléfono de contacto si falta. Haz una sola pregunta cada vez. "
                    "Cuando leas el teléfono, usa phone_spoken para decir los dígitos uno detrás de otro. "
                    "Cuando tengas ambos datos, llama a confirm_reservation. "
                    "No inventes nombre ni teléfono. La reserva confirmada pasará al nodo final, "
                    "que resumirá y se despedirá."
                ),
            }
        ],
        functions=[confirm_reservation, cancel_reservation, return_to_main_menu],
    )
