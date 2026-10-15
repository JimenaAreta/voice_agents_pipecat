"""Pruebas de la estructura conversacional definida en YAML."""

from pipecat.flows import FlowConfig

from flows.restaurant_flow import FLOW_FILE, load_restaurant_flow


def function(node, name):
    """Localiza una herramienta declarada en un nodo de prueba."""
    return next(item for item in node.functions if item.name == name)


def test_declarative_flow_resolves_all_python_handlers():
    flow = load_restaurant_flow()
    assert flow.config.initial_node == "initial"
    assert set(flow.config.nodes) == {
        "initial",
        "ordering",
        "order_confirmation",
        "reservation_date",
        "reservation_party",
        "reservation_time",
        "reservation_no_availability",
        "reservation_details",
        "end",
    }


def test_availability_transition_is_declared_in_yaml():
    config = FlowConfig.from_file(FLOW_FILE)
    tool = function(config.nodes["reservation_time"], "check_reservation_availability")
    assert tool.transition_to.field == "status"
    assert tool.transition_to.cases["disponible"] == "reservation_details"
    assert tool.transition_to.cases["no_disponible"] == "reservation_no_availability"


def test_intent_changes_are_transition_only_tools():
    config = FlowConfig.from_file(FLOW_FILE)
    tool = function(config.nodes["ordering"], "return_to_main_menu")
    assert tool.transition_only is True
    assert tool.transition_to == "initial"
