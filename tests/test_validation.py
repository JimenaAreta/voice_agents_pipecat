import pytest

from config import ConfigurationError, VoiceSettings, validate_required_api_keys
from services.validation import (
    normalize_address,
    normalize_name,
    normalize_phone,
    normalize_reservation_date,
)


def test_contact_validation():
    assert normalize_name("  Ana   López ") == "Ana López"
    assert normalize_name("1") is None
    assert normalize_phone("+34 612 345 678") == "34612345678"
    assert normalize_phone("123") is None
    assert normalize_address(" Calle Mayor, 10 ") == "Calle Mayor, 10"
    assert normalize_address("x") is None
    from datetime import date
    assert normalize_reservation_date(" mañana ", today=date(2026, 10, 18)) == "2026-10-19"


def test_voice_settings_defaults(monkeypatch):
    for name in (
        "TURN_STOP_STRATEGY",
        "VAD_CONFIDENCE",
        "VAD_START_SECS",
        "VAD_STOP_SECS",
        "VAD_MIN_VOLUME",
        "USER_SPEECH_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = VoiceSettings.from_env()
    assert settings.turn_strategy == "smart"
    assert settings.vad_stop_secs == 0.2


def test_voice_settings_reject_invalid_strategy(monkeypatch):
    monkeypatch.setenv("TURN_STOP_STRATEGY", "guess")
    with pytest.raises(ConfigurationError):
        VoiceSettings.from_env()


def test_required_api_keys(monkeypatch):
    for name in ("OPENAI_API_KEY", "DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        validate_required_api_keys()


@pytest.mark.parametrize(("text", "expected"), [
    ("hoy", "2026-10-18"),
    (" MAÑANA ", "2026-10-19"),
    ("pasado mañana", "2026-10-20"),
    ("pasado", "2026-10-20"),
    ("pasado   mañana", "2026-10-20"),
])
def test_relative_reservation_dates(text, expected):
    from datetime import date
    assert normalize_reservation_date(text, today=date(2026, 10, 18)) == expected


@pytest.mark.parametrize(("reference", "expected"), [
    ("2026-12-31", "2027-01-02"),
    ("2028-02-28", "2028-03-01"),
    ("2026-02-28", "2026-03-02"),
])
def test_relative_dates_cross_calendar_boundaries(reference, expected):
    from datetime import date
    assert normalize_reservation_date("pasado", today=date.fromisoformat(reference)) == expected


def test_restaurant_date_uses_madrid_at_utc_day_boundary(monkeypatch):
    from datetime import datetime, timezone
    from services import validation

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz):
            return datetime(2026, 10, 18, 23, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(validation, "datetime", FixedDatetime)
    assert normalize_reservation_date("mañana") == "2026-10-20"
