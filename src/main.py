"""Bot de voz de El Rincón de Castilla con pedido de comida y reserva de mesa.

Este archivo contiene solo el ensamblaje del pipeline de Pipecat. La lógica de
negocio está separada en módulos:

- `ordering.py`: pedido de comida.
- `reservations.py`: reserva de mesa inspirada en `restaurant_reservation.py`.
- `services.py`: OpenAI, Deepgram y ElevenLabs.
- `flow_nodes.py`: nodo inicial que enruta entre pedido y reserva.

Ejecuta con:
    uv run python src/main.py

Después abre:
    http://localhost:7860/client
"""

import aiohttp
import os
from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat_flows import FlowManager

from flows.flow_nodes import create_initial_node
from flows.ordering import get_order_time_estimate
from services.services import create_deepgram_stt, create_elevenlabs_tts, create_openai_llm

load_dotenv(override=True)


# El runner de Pipecat puede crear distintos transportes a partir de argumentos
# de línea de comandos. Para una demo local de máster, el cliente WebRTC por
# defecto es lo más cómodo: `uv run python src/main.py` y después abre
# http://localhost:7860/client.
transport_params = {
    "daily": lambda: DailyParams(audio_in_enabled=True, audio_out_enabled=True),
    "twilio": lambda: FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True),
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


def create_vad_analyzer() -> SileroVADAnalyzer:
    """Crea Silero VAD con parámetros ajustables para cerrar turnos de voz."""
    return SileroVADAnalyzer(
        params=VADParams(
            confidence=float(os.getenv("VAD_CONFIDENCE", "0.7")),
            start_secs=float(os.getenv("VAD_START_SECS", "0.2")),
            stop_secs=float(os.getenv("VAD_STOP_SECS", "0.35")),
            min_volume=float(os.getenv("VAD_MIN_VOLUME", "0.6")),
        )
    )


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    """Construye y ejecuta el pipeline de Pipecat."""
    stt = create_deepgram_stt()
    llm = create_openai_llm()

    # ElevenLabs HTTP necesita una sesión aiohttp compartida. La cerramos cuando
    # el cliente se desconecta para no dejar recursos abiertos.
    aiohttp_session = aiohttp.ClientSession()
    tts = create_elevenlabs_tts(aiohttp_session)

    # El agregador de contexto mantiene el historial de conversación. Silero VAD
    # ayuda a Pipecat a decidir cuándo el usuario ha terminado de hablar antes
    # de enviar el texto al LLM.
    context = LLMContext()
    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            audio_idle_timeout=float(os.getenv("USER_AUDIO_IDLE_TIMEOUT", "0.7")),
            user_turn_stop_timeout=float(os.getenv("USER_TURN_STOP_TIMEOUT", "1.2")),
            vad_analyzer=create_vad_analyzer(),
            filter_incomplete_user_turns=False,
        ),
    )

    # El audio y el texto avanzan por el pipeline de izquierda a derecha:
    # micrófono -> STT -> contexto del usuario -> LLM -> TTS -> altavoz
    # -> contexto del asistente.
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

    task = PipelineTask(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )

    flow_manager = FlowManager(
        task=task,
        llm=llm,
        context_aggregator=context_aggregator,
        transport=transport,
        # Función disponible en cualquier nodo del flujo de pedido.
        global_functions=[get_order_time_estimate],
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client) -> None:
        logger.info("Cliente conectado")
        await flow_manager.initialize(create_initial_node())

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client) -> None:
        logger.info("Cliente desconectado")
        await aiohttp_session.close()
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments) -> None:
    """Punto de entrada usado por `pipecat.runner.run.main`."""
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
