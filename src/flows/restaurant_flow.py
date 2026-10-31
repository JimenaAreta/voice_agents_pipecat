"""Loads the declarative flow and wires it to its Python handlers."""

from pathlib import Path

from pipecat.flows import Flow, FlowConfig

from flows import ordering, reservations
from services import common_nodes


FLOW_FILE = Path(__file__).with_name("restaurant.yaml")


def load_restaurant_flow() -> Flow:
    """Validates the YAML and resolves the names of its Python handlers."""
    config = FlowConfig.from_file(FLOW_FILE)
    return Flow(config, handlers=[ordering, reservations, common_nodes])
