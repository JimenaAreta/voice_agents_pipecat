"""Validated configuration for the voice agent."""

from dataclasses import dataclass
import os


class ConfigurationError(RuntimeError):
    """Indicates that the required configuration to start is invalid."""


def _float_setting(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number, not {raw_value!r}.") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}.")
    return value


@dataclass(frozen=True)
class VoiceSettings:
    """Voice detection and turn end parameters."""

    vad_confidence: float
    vad_start_secs: float
    vad_stop_secs: float
    vad_min_volume: float
    turn_strategy: str
    speech_timeout_secs: float

    @classmethod
    def from_env(cls) -> "VoiceSettings":
        turn_strategy = os.getenv("TURN_STOP_STRATEGY", "smart").strip().lower()
        if turn_strategy not in {"smart", "timeout"}:
            raise ConfigurationError("TURN_STOP_STRATEGY must be 'smart' or 'timeout'.")
        return cls(
            vad_confidence=_float_setting("VAD_CONFIDENCE", 0.7, minimum=0.0, maximum=1.0),
            vad_start_secs=_float_setting("VAD_START_SECS", 0.2, minimum=0.0, maximum=2.0),
            vad_stop_secs=_float_setting("VAD_STOP_SECS", 0.2, minimum=0.1, maximum=2.0),
            vad_min_volume=_float_setting("VAD_MIN_VOLUME", 0.6, minimum=0.0, maximum=1.0),
            turn_strategy=turn_strategy,
            speech_timeout_secs=_float_setting(
                "USER_SPEECH_TIMEOUT", 0.6, minimum=0.2, maximum=5.0
            ),
        )


def validate_required_api_keys() -> None:
    """Fails early and without exposing secrets if a credential is missing."""
    required = ("OPENAI_API_KEY", "DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise ConfigurationError(
            "Missing required environment variables: " + ", ".join(missing)
        )
