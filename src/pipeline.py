"""Construcción de la infraestructura de voz de Pipecat.

Este módulo aparta de ``main.py`` los detalles técnicos del pipeline. Para
seguir el ejemplo basta pensar en esta cadena:

    micrófono -> transcripción -> LLM -> síntesis de voz -> altavoz

Las funciones de esta página explican cómo se configura cada pieza.
"""

from dataclasses import dataclass

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.transports.base_transport import BaseTransport
from pipecat.turns.user_start import (
    TranscriptionUserTurnStartStrategy,
    VADUserTurnStartStrategy,
)
from pipecat.turns.user_stop import (
    SpeechTimeoutUserTurnStopStrategy,
    TurnAnalyzerUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from config import VoiceSettings


@dataclass(frozen=True)
class VoicePipeline:
    """Piezas del pipeline que también necesita el gestor del flujo."""

    pipeline: Pipeline
    context_aggregator: LLMContextAggregatorPair


def create_vad_analyzer(settings: VoiceSettings) -> SileroVADAnalyzer:
    """Detecta cuándo empieza y termina físicamente la voz del usuario."""
    return SileroVADAnalyzer(
        params=VADParams(
            confidence=settings.vad_confidence,
            start_secs=settings.vad_start_secs,
            stop_secs=settings.vad_stop_secs,
            min_volume=settings.vad_min_volume,
        )
    )


def create_user_turn_strategies(settings: VoiceSettings) -> UserTurnStrategies:
    """Decide cuándo una intervención del usuario está completa."""
    if settings.turn_strategy == "timeout":
        stop_strategy = SpeechTimeoutUserTurnStopStrategy(
            user_speech_timeout=settings.speech_timeout_secs
        )
    else:
        stop_strategy = TurnAnalyzerUserTurnStopStrategy(
            turn_analyzer=LocalSmartTurnAnalyzerV3()
        )

    return UserTurnStrategies(
        start=[VADUserTurnStartStrategy(), TranscriptionUserTurnStartStrategy()],
        stop=[stop_strategy],
    )


def create_voice_pipeline(
    transport: BaseTransport,
    stt,
    llm,
    tts,
    settings: VoiceSettings,
) -> VoicePipeline:
    """Construye la cadena que transforma voz en respuesta hablada."""
    context_aggregator = LLMContextAggregatorPair(
        LLMContext(),
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=create_user_turn_strategies(settings),
            vad_analyzer=create_vad_analyzer(settings),
            filter_incomplete_user_turns=False,
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )
    return VoicePipeline(pipeline=pipeline, context_aggregator=context_aggregator)
