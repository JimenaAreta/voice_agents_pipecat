"""Python actions referenced by the declarative flow."""

from loguru import logger
from pipecat.flows import FlowManager


async def check_restaurant_status(action: dict, flow_manager: FlowManager) -> None:
    """Pre-action to demonstrate that a flow can execute code when entering a node."""
    logger.info("The restaurant is open and ready to serve.")
