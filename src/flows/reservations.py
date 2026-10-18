"""Flujo de reservas con disponibilidad y confirmaciones persistentes en SQLite."""

import asyncio
import sqlite3
from uuid import uuid4
from typing import TypedDict

from loguru import logger
from pipecat.flows import FlowManager
from pipecat.flows.types import TRANSITION_IN_YAML

from services.speech_format import (
    format_date_for_speech,
    format_phone_for_speech,
    format_time_for_speech,
    format_times_for_speech,
)
from services.reservation_store import SlotUnavailableError, available_times, save_reservation
from services.validation import normalize_name, normalize_phone, normalize_reservation_date


class ReservationSystem:
    """Consulta la disponibilidad persistida sin bloquear el pipeline de audio."""

    async def check_availability(
        self, party_size: int, reservation_date: str, requested_time: str
    ) -> tuple[bool, list[str]]:
        times = await asyncio.to_thread(available_times, reservation_date)
        available = requested_time in times
        return available, [] if available else times


reservation_system = ReservationSystem()

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
    reservation_date_spoken: str
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
    reservation_date_spoken: str
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
    reservation_date_spoken: str
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


def build_start_result(
    flow_manager: FlowManager,
    status: str,
    *,
    party_size: int = 0,
    requested_time: str = "",
    available: bool | None = None,
    alternative_times: list[str] | None = None,
) -> ReservationStartResult:
    """Construye la respuesta común mientras se recogen los datos básicos."""
    alternatives = alternative_times or []
    return {
        "status": status,
        "reservation_date": flow_manager.state.get("reservation_date") or "",
        "reservation_date_spoken": format_date_for_speech(flow_manager.state.get("reservation_date") or ""),
        "party_size": party_size,
        "requested_time": requested_time,
        "requested_time_spoken": format_time_for_speech(requested_time),
        "available": available,
        "alternative_times": alternatives,
        "alternative_times_spoken": format_times_for_speech(alternatives),
    }


def build_availability_result(
    flow_manager: FlowManager,
    status: str,
    requested_time: str,
    *,
    available: bool = False,
    alternative_times: list[str] | None = None,
) -> AvailabilityResult:
    """Construye una respuesta uniforme para cualquier comprobación de mesa."""
    alternatives = alternative_times or []
    return {
        "status": status,
        "reservation_date": flow_manager.state.get("reservation_date") or "",
        "reservation_date_spoken": format_date_for_speech(flow_manager.state.get("reservation_date") or ""),
        "party_size": flow_manager.state.get("reservation_party_size") or 0,
        "requested_time": requested_time,
        "requested_time_spoken": format_time_for_speech(requested_time),
        "available": available,
        "alternative_times": alternatives,
        "alternative_times_spoken": format_times_for_speech(alternatives),
    }


async def find_available_table(
    flow_manager: FlowManager, requested_time: str
) -> tuple[AvailabilityResult, object]:
    """Consulta disponibilidad; el YAML elegirá la siguiente etapa."""
    party_size = flow_manager.state["reservation_party_size"]
    reservation_date = flow_manager.state["reservation_date"]
    try:
        is_available, alternative_times = await reservation_system.check_availability(
            party_size, reservation_date, requested_time
        )
    except (OSError, sqlite3.Error):
        logger.warning("No se ha podido consultar la disponibilidad")
        flow_manager.state["reservation_time"] = None
        return build_availability_result(
            flow_manager, "error_disponibilidad", requested_time
        ), TRANSITION_IN_YAML
    flow_manager.state["reservation_time"] = requested_time if is_available else None
    flow_manager.state["alternative_times_spoken"] = format_times_for_speech(
        alternative_times
    )

    result = build_availability_result(
        flow_manager,
        "disponible" if is_available else "no_disponible",
        requested_time,
        available=is_available,
        alternative_times=alternative_times,
    )
    if is_available:
        logger.debug("Hora disponible, pasamos a datos de confirmación.")
        return result, TRANSITION_IN_YAML

    logger.debug(f"Hora no disponible. Alternativas: {alternative_times}")
    return result, TRANSITION_IN_YAML


def build_reservation_result(
    flow_manager: FlowManager,
    status: str,
    customer_name: str,
    phone_number: str,
) -> ReservationResult:
    """Resume los datos de confirmación sin repetir claves en cada rama."""
    reservation_time = flow_manager.state.get("reservation_time") or ""
    return {
        "status": status,
        "reservation_date": flow_manager.state.get("reservation_date") or "",
        "reservation_date_spoken": format_date_for_speech(flow_manager.state.get("reservation_date") or ""),
        "party_size": flow_manager.state.get("reservation_party_size") or 0,
        "reservation_time": reservation_time,
        "reservation_time_spoken": format_time_for_speech(reservation_time),
        "customer_name": customer_name,
        "phone_number": phone_number,
        "phone_spoken": format_phone_for_speech(phone_number),
    }


async def start_table_reservation(
    flow_manager: FlowManager,
    reservation_date: str = "",
    party_size: int = 0,
    requested_time: str = "",
) -> tuple[ReservationStartResult, object]:
    """
    Empieza una reserva de mesa desde el nodo inicial.

    Args:
        reservation_date: Día de la reserva, por ejemplo hoy, mañana, viernes o 25 de mayo.
        party_size: Número de personas. Debe estar entre 1 y 12.
        requested_time: Hora opcional de la reserva. Puede ser 19:00, 20:00, ocho de la tarde, etc.
    """
    ensure_reservation_state(flow_manager)
    normalized_date = normalize_reservation_date(reservation_date)
    if normalized_date is None:
        return build_start_result(
            flow_manager, "falta_dia", party_size=party_size, requested_time=requested_time
        ), TRANSITION_IN_YAML

    flow_manager.state["reservation_date"] = normalized_date

    if party_size == 0:
        return build_start_result(
            flow_manager,
            "falta_personas",
            party_size=party_size,
            requested_time=requested_time,
        ), TRANSITION_IN_YAML

    if party_size < 1 or party_size > 12:
        return build_start_result(
            flow_manager,
            "tamaño_no_valido",
            party_size=party_size,
            requested_time=requested_time,
        ), TRANSITION_IN_YAML

    flow_manager.state["reservation_party_size"] = party_size

    if not requested_time.strip():
        return build_start_result(
            flow_manager, "falta_hora", party_size=party_size
        ), TRANSITION_IN_YAML

    normalized_time = normalize_reservation_time(requested_time)
    if normalized_time is None:
        return build_start_result(
            flow_manager,
            "hora_no_valida",
            party_size=party_size,
            requested_time=requested_time,
            alternative_times=sorted(VALID_RESERVATION_TIMES),
        ), TRANSITION_IN_YAML

    result, next_node = await find_available_table(flow_manager, normalized_time)
    return ReservationStartResult(**result), next_node


async def collect_reservation_date(
    flow_manager: FlowManager, reservation_date: str
) -> tuple[dict[str, str], object]:
    """
    Registra el día de la reserva.

    Args:
        reservation_date: Día de la reserva, por ejemplo hoy, mañana, viernes o 25 de mayo.
    """
    ensure_reservation_state(flow_manager)
    normalized_date = normalize_reservation_date(reservation_date)
    if normalized_date is None:
        return {
            "status": "dia_no_valido",
            "reservation_date": "",
        }, TRANSITION_IN_YAML
    flow_manager.state["reservation_date"] = normalized_date
    return {
        "status": "ok",
        "reservation_date": flow_manager.state["reservation_date"],
    }, TRANSITION_IN_YAML


async def collect_party_size(
    flow_manager: FlowManager, party_size: int
) -> tuple[PartySizeResult, object]:
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
        }, TRANSITION_IN_YAML

    if party_size < 1 or party_size > 12:
        return {
            "party_size": party_size,
            "status": "tamaño_no_valido",
        }, TRANSITION_IN_YAML

    flow_manager.state["reservation_party_size"] = party_size
    return {
        "party_size": party_size,
        "status": "ok",
    }, TRANSITION_IN_YAML


async def check_reservation_availability(
    flow_manager: FlowManager, requested_time: str
) -> tuple[AvailabilityResult, object]:
    """
    Comprueba si hay mesa disponible para la hora solicitada.

    Args:
        requested_time: Hora de la reserva en formato 24h. Debe ser una de 18:00, 19:00, 20:00, 21:00 o 22:00.
    """
    ensure_reservation_state(flow_manager)
    if not flow_manager.state.get("reservation_date"):
        return build_availability_result(
            flow_manager, "falta_dia", requested_time
        ), TRANSITION_IN_YAML

    party_size = flow_manager.state.get("reservation_party_size")
    if not party_size:
        return build_availability_result(
            flow_manager, "falta_personas", requested_time
        ), TRANSITION_IN_YAML

    normalized_time = normalize_reservation_time(requested_time)
    if normalized_time is None:
        return build_availability_result(
            flow_manager,
            "hora_no_valida",
            requested_time,
            alternative_times=sorted(VALID_RESERVATION_TIMES),
        ), TRANSITION_IN_YAML

    return await find_available_table(flow_manager, normalized_time)


async def confirm_reservation(
    flow_manager: FlowManager, customer_name: str, phone_number: str
) -> tuple[ReservationResult | AvailabilityResult, object]:
    """
    Confirma la reserva con nombre y teléfono del cliente.

    Args:
        customer_name: Nombre de la persona que reserva.
        phone_number: Teléfono de contacto para la reserva.
    """
    ensure_reservation_state(flow_manager)
    if not flow_manager.state.get("reservation_date"):
        return build_reservation_result(
            flow_manager, "falta_dia", customer_name.strip(), phone_number.strip()
        ), TRANSITION_IN_YAML

    if not flow_manager.state.get("reservation_party_size"):
        return build_reservation_result(
            flow_manager, "falta_personas", customer_name.strip(), phone_number.strip()
        ), TRANSITION_IN_YAML

    if not flow_manager.state.get("reservation_time"):
        return build_reservation_result(
            flow_manager, "falta_hora", customer_name.strip(), phone_number.strip()
        ), TRANSITION_IN_YAML

    normalized_name = normalize_name(customer_name)
    normalized_phone = normalize_phone(phone_number)
    if normalized_name is None or normalized_phone is None:
        return build_reservation_result(
            flow_manager,
            "faltan_datos_contacto",
            normalized_name or "",
            normalized_phone or "",
        ), TRANSITION_IN_YAML

    flow_manager.state["reservation_name"] = normalized_name
    flow_manager.state["reservation_phone"] = normalized_phone

    result = build_reservation_result(
        flow_manager, "reserva_confirmada", normalized_name, normalized_phone
    )
    reservation_id = flow_manager.state.setdefault("reservation_id", str(uuid4()))
    try:
        await asyncio.to_thread(save_reservation, reservation_id, result)
    except SlotUnavailableError:
        return await find_available_table(flow_manager, result["reservation_time"])
    except (OSError, sqlite3.Error):
        # No registrar nombre, teléfono ni detalles de la excepción.
        logger.warning("No se ha podido guardar la reserva")
        result["status"] = "error_guardado"
    return result, TRANSITION_IN_YAML
