"""Creación de servicios externos usados por el pipeline de Pipecat."""

import os

import aiohttp
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsHttpTTSService
from pipecat.services.openai.responses.llm import (
    OpenAIResponsesHttpLLMService,
    OpenAIResponsesLLMService,
)

from services.common_nodes import ROLE_MESSAGE


def create_openai_llm() -> OpenAIResponsesLLMService:
    """Crea el servicio LLM de OpenAI.

    Se usa gpt-4.1-nano porque es un modelo pequeño y económico de OpenAI que
    soporta llamadas a funciones, algo necesario para las funciones directas de
    Pipecat Flows. El límite `max_completion_tokens` también ayuda a mantener
    respuestas habladas cortas.
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
            system_instruction=ROLE_MESSAGE,
            temperature=0.2,
            max_completion_tokens=140,
        ),
    )


def create_deepgram_stt() -> DeepgramSTTService:
    """Crea el servicio STT de Deepgram para transcribir audio en español."""
    settings = {
        "model": os.getenv("DEEPGRAM_MODEL", "nova-3"),
        "language": os.getenv("DEEPGRAM_LANGUAGE", "es"),
        "smart_format": True,
    }
    if os.getenv("DEEPGRAM_ENDPOINTING_MS"):
        settings["endpointing"] = int(os.getenv("DEEPGRAM_ENDPOINTING_MS", "250"))
    if os.getenv("DEEPGRAM_UTTERANCE_END_MS"):
        settings["utterance_end_ms"] = int(os.getenv("DEEPGRAM_UTTERANCE_END_MS", "700"))

    return DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        settings=DeepgramSTTService.Settings(**settings),
    )


def create_elevenlabs_tts(
    aiohttp_session: aiohttp.ClientSession,
) -> ElevenLabsHttpTTSService:
    """Crea el servicio TTS de ElevenLabs.

    Usamos el servicio HTTP en lugar del WebSocket porque algunas cuentas de
    ElevenLabs rechazan cambios de `voice_settings` entre contextos WebSocket.
    Sigue siendo streaming de audio de ElevenLabs, pero evita ese error 1008.
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
