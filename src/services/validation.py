"""Validaciones deterministas para datos recibidos por herramientas del LLM."""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def normalize_phone(phone_number: str) -> str | None:
    """Normaliza un teléfono razonable sin aceptar texto vacío o incompleto."""
    digits = re.sub(r"\D", "", phone_number)
    if not 9 <= len(digits) <= 15:
        return None
    return digits


def normalize_name(name: str) -> str | None:
    """Limpia un nombre y rechaza valores vacíos o claramente inválidos."""
    clean_name = " ".join(name.split())
    if len(clean_name) < 2 or len(clean_name) > 80:
        return None
    if not any(character.isalpha() for character in clean_name):
        return None
    return clean_name


def normalize_address(address: str) -> str | None:
    """Limpia una dirección de entrega básica."""
    clean_address = " ".join(address.split())
    if len(clean_address) < 5 or len(clean_address) > 200:
        return None
    return clean_address


def restaurant_today() -> date:
    """Fecha del restaurante, independiente de la zona horaria del servidor."""
    return datetime.now(ZoneInfo("Europe/Madrid")).date()


def normalize_reservation_date(date_text: str, *, today: date | None = None) -> str | None:
    """Resuelve días relativos a ISO; conserva otras fechas habladas."""
    clean_date = " ".join(date_text.split())
    if len(clean_date) < 3 or len(clean_date) > 80:
        return None
    relative_days = {"hoy": 0, "mañana": 1, "pasado mañana": 2, "pasado": 2}
    offset = relative_days.get(clean_date.casefold())
    if offset is not None:
        reference = today if today is not None else restaurant_today()
        return (reference + timedelta(days=offset)).isoformat()
    return clean_date
