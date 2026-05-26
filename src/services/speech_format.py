"""Utilidades para preparar textos que se pronuncian mejor por TTS."""

import re


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
