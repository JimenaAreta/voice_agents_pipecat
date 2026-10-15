"""Bot de voz de El Rincón de Castilla con pedido de comida y reserva de mesa.

Este archivo contiene solo el ensamblaje de la aplicación. El resto está
separado por responsabilidad:

- `restaurant.yaml`: nodos, prompts y transiciones del flujo.
- `ordering.py`: pedido de comida.
- `reservations.py`: reserva de mesa.
- `services.py`: OpenAI, Deepgram y ElevenLabs.
- `pipeline.py`: procesamiento de voz y turnos.

Ejecuta con:
    uv run python src/main.py

Después abre:
    http://localhost:7860/client
"""

import aiohttp
from dotenv import load_dotenv
from loguru import logger
from pipecat.pipeline.runner import WorkerRunner
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.flows import FlowManager

from config import VoiceSettings, validate_required_api_keys
from flows.restaurant_flow import load_restaurant_flow
from pipeline import create_voice_pipeline
from services.menu import format_menu_for_prompt
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


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    """Prepara los servicios, el flujo conversacional y ejecuta el bot."""
    validate_required_api_keys()
    voice_settings = VoiceSettings.from_env()
    stt = create_deepgram_stt()
    llm = create_openai_llm()

    # ElevenLabs HTTP necesita una sesión aiohttp compartida. La cerramos cuando
    # el cliente se desconecta para no dejar recursos abiertos.
    aiohttp_session = aiohttp.ClientSession()

    # El agregador de contexto mantiene el historial de conversación. Silero VAD
    # ayuda a Pipecat a decidir cuándo el usuario ha terminado de hablar antes
    # de enviar el texto al LLM.
    try:
        tts = create_elevenlabs_tts(aiohttp_session)
        voice_pipeline = create_voice_pipeline(
            transport=transport,
            stt=stt,
            llm=llm,
            tts=tts,
            settings=voice_settings,
        )
        restaurant_flow = load_restaurant_flow()

        worker = PipelineWorker(
            voice_pipeline.pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
                report_only_initial_ttfb=False,
            ),
            idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
        )

        flow_manager = FlowManager(
            worker=worker,
            llm=llm,
            context_aggregator=voice_pipeline.context_aggregator,
            transport=transport,
            global_functions=restaurant_flow.global_functions,
        )

        runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client) -> None:
            logger.info("Cliente conectado; inicializando flujo")
            # Cada conexión representa un cliente nuevo. Así ningún nombre,
            # teléfono o pedido de una conversación anterior puede heredarse.
            flow_manager.state.clear()
            flow_manager.state["menu_prompt"] = format_menu_for_prompt()
            flow_manager.state["alternative_times_spoken"] = ""
            await flow_manager.initialize(restaurant_flow.initial_node)

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client) -> None:
            logger.info("Cliente desconectado; cancelando sesión")
            await runner.cancel()

        await runner.add_workers(worker)
        await runner.run()
    finally:
        if not aiohttp_session.closed:
            await aiohttp_session.close()


async def bot(runner_args: RunnerArguments) -> None:
    """Punto de entrada usado por `pipecat.runner.run.main`."""
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
