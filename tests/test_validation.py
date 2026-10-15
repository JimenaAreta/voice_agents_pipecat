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
    assert normalize_reservation_date(" mañana ") == "mañana"


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
