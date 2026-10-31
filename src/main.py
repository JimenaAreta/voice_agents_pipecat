"""Voice bot for El Rincón de Castilla with food ordering and table reservation.

This file contains only application assembly. The rest is separated by responsibility:

- `restaurant.yaml`: flow nodes, prompts, and transitions.
- `ordering.py`: food ordering.
- `reservations.py`: table reservation.
- `services.py`: OpenAI, Deepgram, and ElevenLabs.
- `pipeline.py`: voice processing and turn handling.

Run with:
    uv run python src/main.py

Then open:
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


# Pipecat's runner can create different transports from command-line arguments.
# For a local demo, the default WebRTC client is the most convenient: `uv run python src/main.py`
# and then open http://localhost:7860/client.
transport_params = {
    "daily": lambda: DailyParams(audio_in_enabled=True, audio_out_enabled=True),
    "twilio": lambda: FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True),
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    """Prepares the services, the conversational flow, and runs the bot."""
    validate_required_api_keys()
    voice_settings = VoiceSettings.from_env()
    stt = create_deepgram_stt()
    llm = create_openai_llm()

    # ElevenLabs HTTP needs a shared aiohttp session. We close it when the client disconnects
    # to avoid leaving resources open.
    aiohttp_session = aiohttp.ClientSession()

    # The context aggregator keeps the conversation history. Silero VAD helps Pipecat decide
    # when the user has finished speaking before sending the text to the LLM.
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
            logger.info("Client connected; initializing flow")
            # Each connection represents a new client. This ensures no name, phone, or previous
            # order can be inherited across conversations.
            flow_manager.state.clear()
            flow_manager.state["menu_prompt"] = format_menu_for_prompt()
            flow_manager.state["alternative_times_spoken"] = ""
            await flow_manager.initialize(restaurant_flow.initial_node)

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client) -> None:
            logger.info("Client disconnected; canceling session")
            await runner.cancel()

        await runner.add_workers(worker)
        await runner.run()
    finally:
        if not aiohttp_session.closed:
            await aiohttp_session.close()


async def bot(runner_args: RunnerArguments) -> None:
    """Entry point used by `pipecat.runner.run.main`."""
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
