"""Nodo inicial que enruta entre pedido de comida y reserva de mesa."""

from pipecat_flows import FlowManager, NodeConfig

from flows.ordering import (
    add_menu_item,
    add_multiple_menu_items,
    begin_food_order,
    prepare_checkout,
    remove_menu_item,
)
from flows.reservations import start_table_reservation
from services.common_nodes import ROLE_MESSAGE, check_restaurant_status
from services.menu import format_menu_for_prompt


def create_initial_node(respond_immediately: bool = True) -> NodeConfig:
    """Crea el nodo inicial y permite empezar pedido o reserva sin perder datos."""
    return NodeConfig(
        name="initial",
        role_message=ROLE_MESSAGE,
        task_messages=[
            {
                "role": "developer",
                "content": f"""Al conectarte, empieza siempre con una sola frase, sin llamar a herramientas:
Hola, gracias por llamar a El Rincón de Castilla, ¿quiere hacer un pedido de comida o reservar una mesa?

No inventes datos y no llames a herramientas hasta que el cliente responda.
La presentación inicial debe ser una única frase, sin punto intermedio, para que si el cliente interrumpe no quede otra frase pendiente.
Si llegas a este nodo desde otro flujo, no repitas el saludo inicial.

Pedido:
- Si solo dice que quiere pedir comida, llama a begin_food_order.
- Si el cliente ya está haciendo un pedido y dice algo ambiguo como "un poco de todo",
  pregunta una aclaración; no vuelvas al saludo.
- Si pide un producto concreto con cantidad, llama directamente a add_menu_item.
- Si pide varios productos con cantidades, llama una sola vez a add_multiple_menu_items.
- Si pide un producto pero falta cantidad, pregunta la cantidad.
- Si quiere cambiar un producto, llama a remove_menu_item.
- Si quiere finalizar un pedido, llama a prepare_checkout solo si tienes nombre, teléfono,
  tipo de pedido y dirección si es entrega.
- Para recogida, el teléfono es obligatorio.
- Para entrega, teléfono y dirección son obligatorios.

Reserva:
- Para reservar hacen falta siempre tres datos antes de comprobar disponibilidad:
  día, número de personas y hora.
- Si quiere reservar pero no da el día, pregunta solo el día.
- Si da personas u hora pero no da el día, pregunta el día y no asumas "hoy" ni "mañana".
- Si da el día pero falta el número de personas, llama a start_table_reservation con reservation_date.
- Si da día y número de personas pero falta hora, llama a start_table_reservation con reservation_date y party_size.
- Si da día, número de personas y hora, llama a start_table_reservation con reservation_date, party_size y requested_time.

Puedes mencionar el menú si el cliente pregunta por comida:
{format_menu_for_prompt()}

No cierres la conversación desde este nodo. El cierre debe ocurrir después de confirmar un pedido o una reserva.
Mantén respuestas habladas breves porque ElevenLabs las leerá en voz alta.""",
            }
        ],
        pre_actions=[{"type": "function", "handler": check_restaurant_status}],
        functions=[
            begin_food_order,
            add_menu_item,
            add_multiple_menu_items,
            remove_menu_item,
            prepare_checkout,
            start_table_reservation,
        ],
        respond_immediately=respond_immediately,
    )
