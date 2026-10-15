"""Carga el flujo declarativo y lo conecta con sus handlers Python."""

from pathlib import Path

from pipecat.flows import Flow, FlowConfig

from flows import ordering, reservations
from services import common_nodes


FLOW_FILE = Path(__file__).with_name("restaurant.yaml")


def load_restaurant_flow() -> Flow:
    """Valida el YAML y resuelve los nombres de sus handlers Python."""
    config = FlowConfig.from_file(FLOW_FILE)
    return Flow(config, handlers=[ordering, reservations, common_nodes])
