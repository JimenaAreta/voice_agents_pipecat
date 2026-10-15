"""Validaciones deterministas para datos recibidos por herramientas del LLM."""

import re


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


def normalize_reservation_date(date_text: str) -> str | None:
    """Acepta fechas habladas sin inventar interpretación calendárica."""
    clean_date = " ".join(date_text.split())
    if len(clean_date) < 3 or len(clean_date) > 80:
        return None
    return clean_date
