"""Nodos y acciones compartidas por los flujos del restaurante."""

from loguru import logger
from pipecat_flows import FlowManager, NodeConfig


ROLE_MESSAGE = (
    "Eres el asistente de voz de El Rincón de Castilla, un restaurante español. "
    "Debes usar las funciones disponibles para avanzar en la conversación. "
    "Esta es una conversación telefónica, así que responde de forma breve, "
    "natural y fácil de pronunciar. No uses markdown, emojis, viñetas ni "
    "formatos especiales. Habla siempre en español. Cuando digas precios, "
    "usa euros y coma decimal, por ejemplo: 8,50 euros. No digas dólares ni "
    "pronuncies puntos decimales. Lee los teléfonos dígito a dígito, por ejemplo: "
    "seis uno dos tres cuatro cinco seis siete ocho. Para horas de reserva, di "
    "las seis de la tarde, las siete de la tarde, las ocho de la tarde, las nueve "
    "de la noche o las diez de la noche, no dieciocho cero cero. Haz una sola "
    "pregunta cada vez. No inventes datos que el cliente no haya dado. Antes de cerrar un pedido o una reserva, "
    "resume los datos importantes y pide confirmación. Termina siempre con una "
    "despedida amable. Cuando saludes al iniciar la llamada, hazlo en una sola "
    "frase breve."
)


async def check_restaurant_status(action: dict, flow_manager: FlowManager) -> None:
    """Preacción para demostrar que un flujo puede ejecutar código al entrar en un nodo."""
    logger.info("El restaurante está abierto y listo para atender.")


async def return_to_main_menu(flow_manager: FlowManager) -> tuple[None, NodeConfig]:
    """
    Vuelve al nodo inicial cuando el cliente cambia de intención.
    """
    # Import local para evitar un ciclo de importación: common_nodes -> flow_nodes.
    from flows.flow_nodes import create_initial_node

    return None, create_initial_node(respond_immediately=False)


def create_end_node() -> NodeConfig:
    """Crea el nodo final y termina la conversación."""
    return NodeConfig(
        name="end",
        task_messages=[
            {
                "role": "developer",
                "content": (
                    "Da las gracias al cliente. Si el resultado anterior contiene "
                    "un pedido o una reserva, resume esos datos de forma breve. "
                    "Si hay campos phone_spoken, reservation_time_spoken o "
                    "requested_time_spoken, úsalos al hablar en vez de los valores numéricos. "
                    "Termina siempre con una despedida clara, por ejemplo: "
                    "Gracias por llamar a El Rincón de Castilla. Que tenga un buen día."
                ),
            }
        ],
        post_actions=[{"type": "end_conversation"}],
    )
