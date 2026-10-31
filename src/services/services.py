"""Creation of external services used by the Pipecat pipeline."""

import os

import aiohttp
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsHttpTTSService
from pipecat.services.openai.responses.llm import (
    OpenAIResponsesHttpLLMService,
    OpenAIResponsesLLMService,
)


def create_openai_llm() -> OpenAIResponsesLLMService:
    """Creates the OpenAI LLM service.

    gpt-4.1-nano is used because it is a small, cost-effective OpenAI model that
    supports function calling, which is required for direct Pipecat Flows tools.
    The `max_completion_tokens` cap also keeps spoken responses short.
    """
    llm_transport = os.getenv("OPENAI_LLM_TRANSPORT", "http").strip().lower()
    llm_service = (
        OpenAIResponsesLLMService
        if llm_transport in {"websocket", "ws"}
        else OpenAIResponsesHttpLLMService
    )

    return llm_service(
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=llm_service.Settings(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-nano"),
            temperature=0.2,
            max_completion_tokens=140,
        ),
    )


def create_deepgram_stt() -> DeepgramSTTService:
    """Creates the Deepgram STT service for transcribing Spanish audio."""
    settings = {
        "model": os.getenv("DEEPGRAM_MODEL", "nova-3"),
        "language": os.getenv("DEEPGRAM_LANGUAGE", "es"),
        "smart_format": True,
    }
    if os.getenv("DEEPGRAM_ENDPOINTING_MS"):
        settings["endpointing"] = int(os.getenv("DEEPGRAM_ENDPOINTING_MS", "250"))
    if os.getenv("DEEPGRAM_UTTERANCE_END_MS"):
        settings["utterance_end_ms"] = int(os.getenv("DEEPGRAM_UTTERANCE_END_MS", "700"))

    service_kwargs = {
        "api_key": os.getenv("DEEPGRAM_API_KEY"),
        "settings": DeepgramSTTService.Settings(**settings),
    }
    if os.getenv("DEEPGRAM_TTFS_P99_LATENCY"):
        service_kwargs["ttfs_p99_latency"] = float(os.environ["DEEPGRAM_TTFS_P99_LATENCY"])
    return DeepgramSTTService(**service_kwargs)


def create_elevenlabs_tts(
    aiohttp_session: aiohttp.ClientSession,
) -> ElevenLabsHttpTTSService:
    """Creates the ElevenLabs TTS service.

    We use the HTTP service instead of WebSocket because some ElevenLabs accounts
    reject `voice_settings` changes between WebSocket contexts. It is still
    streaming audio from ElevenLabs, but it avoids error 1008.
    """
    return ElevenLabsHttpTTSService(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
        aiohttp_session=aiohttp_session,
        settings=ElevenLabsHttpTTSService.Settings(
            voice=os.getenv("ELEVENLABS_VOICE_ID", "ErXwobaYiN019PkySvjV"),
            model=os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5"),
            language=os.getenv("ELEVENLABS_LANGUAGE", "es"),
        ),
    )
