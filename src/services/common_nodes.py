"""Acciones Python referenciadas por el flujo declarativo."""

from loguru import logger
from pipecat.flows import FlowManager


async def check_restaurant_status(action: dict, flow_manager: FlowManager) -> None:
    """Preacción para demostrar que un flujo puede ejecutar código al entrar en un nodo."""
    logger.info("El restaurante está abierto y listo para atender.")
