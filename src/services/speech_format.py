"""Utilidades para preparar textos que se pronuncian mejor por TTS."""

import re
from decimal import Decimal


DIGIT_WORDS = {
    "0": "cero",
    "1": "uno",
    "2": "dos",
    "3": "tres",
    "4": "cuatro",
    "5": "cinco",
    "6": "seis",
    "7": "siete",
    "8": "ocho",
    "9": "nueve",
}

TIME_SPEECH = {
    "18:00": "las seis de la tarde",
    "19:00": "las siete de la tarde",
    "20:00": "las ocho de la tarde",
    "21:00": "las nueve de la noche",
    "22:00": "las diez de la noche",
}


_UNITS = (
    "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
    "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete",
    "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés",
    "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve",
)

_TENS = {
    30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta",
    70: "setenta", 80: "ochenta", 90: "noventa",
}


def _number_under_100(number: int) -> str:
    if number < 30:
        return _UNITS[number]
    tens, units = divmod(number, 10)
    base = _TENS[tens * 10]
    return base if units == 0 else f"{base} y {_UNITS[units]}"


def _number_under_1000(number: int) -> str:
    if number < 100:
        return _number_under_100(number)
    if number == 100:
        return "cien"
    hundreds, remainder = divmod(number, 100)
    prefix = "ciento" if hundreds == 1 else {
        2: "doscientos", 3: "trescientos", 4: "cuatrocientos",
        5: "quinientos", 6: "seiscientos", 7: "setecientos",
        8: "ochocientos", 9: "novecientos",
    }[hundreds]
    return prefix if remainder == 0 else f"{prefix} {_number_under_100(remainder)}"


def format_euros_for_speech(amount: Decimal | float | int) -> str:
    """Expresa un importe con palabras para evitar lecturas ambiguas del TTS."""
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    euros = int(value)
    cents = int((value - euros) * 100)
    if not 0 <= euros < 1000:
        return f"{str(value).replace('.', ',')} euros"

    euro_unit = "euro" if euros == 1 else "euros"
    euro_words = _number_under_1000(euros)
    if euro_words.endswith("veintiuno"):
        euro_words = euro_words[:-9] + "veintiún"
    elif euro_words.endswith(" y uno"):
        euro_words = euro_words[:-6] + " y un"
    elif euro_words.endswith("uno"):
        euro_words = euro_words[:-3] + "un"
    spoken = f"{euro_words} {euro_unit}"
    if cents:
        cent_unit = "céntimo" if cents == 1 else "céntimos"
        spoken += f" con {_number_under_100(cents)} {cent_unit}"
    return spoken


def format_phone_for_speech(phone_number: str) -> str:
    """Devuelve un teléfono como dígitos leídos uno detrás de otro."""
    digits = re.sub(r"\D", "", phone_number)
    if not digits:
        return phone_number.strip()

    return " ".join(DIGIT_WORDS[digit] for digit in digits)


def format_time_for_speech(time_text: str) -> str:
    """Devuelve una hora de reserva en lenguaje natural para castellano."""
    return TIME_SPEECH.get(time_text, time_text)


def format_times_for_speech(times: list[str]) -> str:
    """Devuelve varias horas en lenguaje natural, separadas por comas."""
    return ", ".join(format_time_for_speech(time) for time in times)
