from services.speech_format import (
    format_euros_for_speech,
    format_phone_for_speech,
    format_time_for_speech,
    format_times_for_speech,
)


def test_money_is_spoken_naturally():
    assert format_euros_for_speech(67) == "sesenta y siete euros"
    assert format_euros_for_speech("8.50") == "ocho euros con cincuenta céntimos"
    assert format_euros_for_speech("1.01") == "un euro con uno céntimo"
    assert format_euros_for_speech(21) == "veintiún euros"


def test_phone_is_spoken_digit_by_digit():
    assert format_phone_for_speech("612 345 678") == (
        "seis uno dos tres cuatro cinco seis siete ocho"
    )


def test_reservation_times_are_natural_spanish():
    assert format_time_for_speech("19:00") == "las siete de la tarde"
    assert format_times_for_speech(["18:00", "22:00"]) == (
        "las seis de la tarde, las diez de la noche"
    )


def test_numeric_dates_are_spoken_without_changing_natural_dates():
    from services.speech_format import format_date_for_speech

    assert format_date_for_speech("12/10") == "el doce de octubre"
    assert format_date_for_speech("2026-10-12") == "el doce de octubre de 2026"
    assert format_date_for_speech("mañana") == "mañana"
    assert format_date_for_speech("31/02") == "31/02"
    assert format_date_for_speech("29/02/2025") == "29/02/2025"
