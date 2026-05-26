"""Flujo de pedido de comida con funciones directas de Pipecat Flows."""

from datetime import datetime, timedelta
from typing import NotRequired, TypedDict

from pipecat_flows import FlowManager, NodeConfig

from services.common_nodes import create_end_node, return_to_main_menu
from services.menu import MENU, format_euros, format_menu_for_prompt
from services.speech_format import format_phone_for_speech


class OrderItem(TypedDict):
    """Línea individual del pedido almacenada en el estado del flujo."""

    item_key: str
    name: str
    quantity: int
    unit_price: float
    line_total: float
    notes: str


class MenuItemRequest(TypedDict):
    """Producto pedido por el cliente antes de convertirlo en línea de pedido."""

    item_key: str
    quantity: int
    notes: NotRequired[str]


class OrderResult(TypedDict):
    """Resultado que la herramienta devuelve al LLM tras cambiar el pedido."""

    status: str
    order_summary: str
    total: float
    total_text: str
    customer_name: NotRequired[str]
    phone_number: NotRequired[str]
    phone_spoken: NotRequired[str]
    order_type: NotRequired[str]
    delivery_address: NotRequired[str]


class DeliveryEstimateResult(TypedDict):
    """Resultado de la función global de estimación de entrega o recogida."""

    estimated_time: str


def ensure_order_state(flow_manager: FlowManager) -> None:
    """Inicializa el estado compartido del pedido la primera vez que se necesita."""
    flow_manager.state.setdefault("order_items", [])
    flow_manager.state.setdefault("customer_name", None)
    flow_manager.state.setdefault("order_type", "recogida")
    flow_manager.state.setdefault("order_phone", None)
    flow_manager.state.setdefault("delivery_address", None)


def order_total(items: list[OrderItem]) -> float:
    """Calcula el total actual del pedido."""
    return round(sum(item["line_total"] for item in items), 2)


def summarize_order(items: list[OrderItem]) -> str:
    """Crea un resumen legible del pedido para que el asistente lo lea en voz alta."""
    if not items:
        return "El pedido está vacío."

    lines = [
        f"{item['quantity']} {item['name']}"
        + (f" con notas: {item['notes']}" if item["notes"] else "")
        + f" ({format_euros(item['line_total'])})"
        for item in items
    ]
    return "; ".join(lines)


def build_order_item(item_key: str, quantity: int, notes: str = "") -> OrderItem:
    """Construye una línea de pedido ya validada."""
    menu_item = MENU[item_key]
    line_total = round(menu_item["price"] * quantity, 2)
    return {
        "item_key": item_key,
        "name": menu_item["name"],
        "quantity": quantity,
        "unit_price": menu_item["price"],
        "line_total": line_total,
        "notes": notes.strip(),
    }


def validate_menu_request(item_key: str, quantity: int) -> str | None:
    """Devuelve un mensaje de error si la línea de pedido no es válida."""
    if item_key not in MENU:
        return f"Clave de producto desconocida: {item_key}."
    if quantity < 1 or quantity > 10:
        return "La cantidad debe estar entre 1 y 10."
    return None


async def add_menu_item(
    flow_manager: FlowManager, item_key: str, quantity: int, notes: str = ""
) -> tuple[OrderResult, NodeConfig]:
    """
    Añade un producto del menú al pedido actual.

    Args:
        item_key: Clave del producto. Debe ser una de las claves del menú.
        quantity: Cantidad solicitada por el cliente. Debe estar entre 1 y 10.
        notes: Notas opcionales de preparación, como sin cebolla o más salsa.
    """
    ensure_order_state(flow_manager)

    # El LLM debería elegir una clave válida, pero esta validación hace la demo
    # más robusta y permite explicar por qué nunca confiamos ciegamente en tools.
    validation_error = validate_menu_request(item_key, quantity)
    if validation_error:
        return {
            "status": "error",
            "order_summary": f"{validation_error} Pide al cliente que lo repita.",
            "total": order_total(flow_manager.state["order_items"]),
            "total_text": format_euros(order_total(flow_manager.state["order_items"])),
        }, create_ordering_node()

    flow_manager.state["order_items"].append(build_order_item(item_key, quantity, notes))

    return {
        "status": "añadido",
        "order_summary": summarize_order(flow_manager.state["order_items"]),
        "total": order_total(flow_manager.state["order_items"]),
        "total_text": format_euros(order_total(flow_manager.state["order_items"])),
    }, create_ordering_node()


async def add_multiple_menu_items(
    flow_manager: FlowManager, items: list[MenuItemRequest]
) -> tuple[OrderResult, NodeConfig]:
    """
    Añade varios productos al pedido actual con una sola llamada de herramienta.

    Args:
        items: Lista de productos. Cada elemento debe incluir item_key y quantity.
            notes es opcional para indicar detalles como sin cebolla.
    """
    ensure_order_state(flow_manager)

    if not items:
        return {
            "status": "error",
            "order_summary": "No se ha recibido ningún producto para añadir.",
            "total": order_total(flow_manager.state["order_items"]),
            "total_text": format_euros(order_total(flow_manager.state["order_items"])),
        }, create_ordering_node()

    new_items: list[OrderItem] = []
    for request in items:
        item_key = request["item_key"]
        quantity = request["quantity"]
        validation_error = validate_menu_request(item_key, quantity)
        if validation_error:
            return {
                "status": "error",
                "order_summary": (
                    f"{validation_error} No he añadido ningún producto del lote. "
                    "Pide al cliente que confirme de nuevo el pedido."
                ),
                "total": order_total(flow_manager.state["order_items"]),
                "total_text": format_euros(order_total(flow_manager.state["order_items"])),
            }, create_ordering_node()

        new_items.append(build_order_item(item_key, quantity, request.get("notes", "")))

    flow_manager.state["order_items"].extend(new_items)

    return {
        "status": "añadidos",
        "order_summary": summarize_order(flow_manager.state["order_items"]),
        "total": order_total(flow_manager.state["order_items"]),
        "total_text": format_euros(order_total(flow_manager.state["order_items"])),
    }, create_ordering_node()


async def begin_food_order(flow_manager: FlowManager) -> tuple[None, NodeConfig]:
    """
    El cliente quiere hacer un pedido de comida, pero todavía no ha indicado productos.
    """
    ensure_order_state(flow_manager)
    return None, create_ordering_node()


async def remove_menu_item(
    flow_manager: FlowManager, item_key: str
) -> tuple[OrderResult, NodeConfig]:
    """
    Elimina un producto del menú del pedido actual.

    Args:
        item_key: Clave del producto que el cliente quiere eliminar.
    """
    ensure_order_state(flow_manager)

    before = len(flow_manager.state["order_items"])
    flow_manager.state["order_items"] = [
        item for item in flow_manager.state["order_items"] if item["item_key"] != item_key
    ]

    status = "eliminado" if len(flow_manager.state["order_items"]) < before else "no_encontrado"
    return {
        "status": status,
        "order_summary": summarize_order(flow_manager.state["order_items"]),
        "total": order_total(flow_manager.state["order_items"]),
        "total_text": format_euros(order_total(flow_manager.state["order_items"])),
    }, create_ordering_node()


async def prepare_checkout(
    flow_manager: FlowManager,
    customer_name: str,
    phone_number: str,
    order_type: str,
    delivery_address: str = "",
) -> tuple[OrderResult, NodeConfig]:
    """
    Pasa a la confirmación cuando el cliente está listo para terminar.

    Args:
        customer_name: Nombre del cliente para el pedido.
        phone_number: Teléfono de contacto para el pedido.
        order_type: Tipo de pedido: recogida o entrega.
        delivery_address: Dirección de entrega. Obligatoria si order_type es entrega.
    """
    ensure_order_state(flow_manager)
    flow_manager.state["customer_name"] = customer_name.strip()
    flow_manager.state["order_phone"] = phone_number.strip()
    requested_order_type = order_type.strip().lower()
    if requested_order_type in {"entrega", "domicilio", "a domicilio"}:
        flow_manager.state["order_type"] = "entrega"
        flow_manager.state["delivery_address"] = delivery_address.strip()
    else:
        flow_manager.state["order_type"] = "recogida"
        flow_manager.state["delivery_address"] = None

    if not flow_manager.state["order_items"]:
        return {
            "status": "pedido_vacio",
            "order_summary": "El cliente todavía no ha pedido ningún producto.",
            "total": 0.0,
            "total_text": format_euros(0.0),
        }, create_ordering_node()

    if not flow_manager.state["order_phone"]:
        return {
            "status": "falta_telefono",
            "order_summary": "Falta el teléfono de contacto del cliente.",
            "total": order_total(flow_manager.state["order_items"]),
            "total_text": format_euros(order_total(flow_manager.state["order_items"])),
        }, create_ordering_node()

    if flow_manager.state["order_type"] == "entrega" and not flow_manager.state["delivery_address"]:
        return {
            "status": "falta_direccion",
            "order_summary": "Falta la dirección de entrega del cliente.",
            "total": order_total(flow_manager.state["order_items"]),
            "total_text": format_euros(order_total(flow_manager.state["order_items"])),
        }, create_ordering_node()

    return {
        "status": "listo_para_confirmar",
        "order_summary": summarize_order(flow_manager.state["order_items"]),
        "total": order_total(flow_manager.state["order_items"]),
        "total_text": format_euros(order_total(flow_manager.state["order_items"])),
        "customer_name": flow_manager.state["customer_name"],
        "phone_number": flow_manager.state["order_phone"],
        "phone_spoken": format_phone_for_speech(flow_manager.state["order_phone"]),
        "order_type": flow_manager.state["order_type"],
        "delivery_address": flow_manager.state["delivery_address"] or "",
    }, create_order_confirmation_node()


async def revise_order(flow_manager: FlowManager) -> tuple[None, NodeConfig]:
    """
    Vuelve al paso de pedido porque el cliente quiere cambiar algo.
    """
    return None, create_ordering_node()


async def complete_order(flow_manager: FlowManager) -> tuple[OrderResult, NodeConfig]:
    """
    Completa el pedido cuando el cliente confirma que todos los datos son correctos.
    """
    ensure_order_state(flow_manager)

    return {
        "status": "completado",
        "order_summary": summarize_order(flow_manager.state["order_items"]),
        "total": order_total(flow_manager.state["order_items"]),
        "total_text": format_euros(order_total(flow_manager.state["order_items"])),
        "customer_name": flow_manager.state["customer_name"] or "",
        "phone_number": flow_manager.state["order_phone"] or "",
        "phone_spoken": format_phone_for_speech(flow_manager.state["order_phone"] or ""),
        "order_type": flow_manager.state["order_type"],
        "delivery_address": flow_manager.state["delivery_address"] or "",
    }, create_end_node()


async def get_order_time_estimate(
    flow_manager: FlowManager,
) -> tuple[DeliveryEstimateResult, None]:
    """Proporciona la estimación actual de recogida o entrega."""
    ensure_order_state(flow_manager)
    minutes = 45 if flow_manager.state["order_type"] == "entrega" else 20
    estimated_time = datetime.now() + timedelta(minutes=minutes)
    return {
        "estimated_time": estimated_time.strftime("%H:%M"),
    }, None


def create_ordering_node() -> NodeConfig:
    """Crea el nodo donde el asistente añade, elimina y actualiza productos."""
    return NodeConfig(
        name="ordering",
        task_messages=[
            {
                "role": "developer",
                "content": f"""Toma el pedido del cliente para el restaurante con un estilo telefónico claro.

Menú:
{format_menu_for_prompt()}

Objetivo:
1. Ayudar al cliente a elegir productos.
2. Añadir o quitar productos con herramientas.
3. Preguntar si quiere algo más después de cada cambio.
4. Antes de finalizar, recoger nombre, teléfono y si es recogida o entrega.
5. Si es entrega, recoger también dirección completa.
6. Pasar a confirmación con prepare_checkout.

Reglas:
- Haz una sola pregunta cada vez.
- Si el cliente dice "un poco de todo", "de todo un poco" o algo parecido,
  no llames a herramientas todavía. Pregunta si quiere una unidad de cada plato
  del menú o si prefiere que le prepares una selección.
- Si el cliente pide un producto pero falta cantidad, pregunta la cantidad.
- Si el cliente pide cantidad y un solo producto, llama a add_menu_item.
- Si el cliente pide varios productos en la misma frase, llama una sola vez a add_multiple_menu_items.
- Después de add_menu_item, add_multiple_menu_items o remove_menu_item, confirma brevemente el resumen del pedido y pregunta si quiere algo más.
- Si el cliente cambia de opinión, llama a remove_menu_item.
- Si el cliente pregunta qué hay en el menú, resume dos o tres opciones y pregunta qué desea.
- Llama a return_to_main_menu solo si el cliente dice claramente que quiere dejar el pedido y reservar mesa.
- Si es recogida, pide teléfono de contacto.
- Si es entrega, pide teléfono y dirección de entrega.
- No finalices hasta tener productos, nombre, teléfono, tipo de pedido y dirección si es entrega.
- Mantén respuestas habladas breves porque ElevenLabs las leerá en voz alta.""",
            }
        ],
        functions=[
            add_menu_item,
            add_multiple_menu_items,
            remove_menu_item,
            prepare_checkout,
            return_to_main_menu,
        ],
    )


def create_order_confirmation_node() -> NodeConfig:
    """Crea el nodo que repasa el pedido antes de enviarlo definitivamente."""
    return NodeConfig(
        name="order_confirmation",
        task_messages=[
            {
                "role": "developer",
                "content": (
                    "Lee el pedido completo, el nombre del cliente, si es recogida "
                    "o entrega, el teléfono y, si es entrega, la dirección. "
                    "Para leer el teléfono usa phone_spoken, no phone_number. "
                    "Da el desglose por producto usando order_summary y después el total "
                    "con total_text. No digas solo el total. Pregunta si todo es correcto. "
                    "No hagas otra pregunta hasta que confirme o pida cambios. "
                    "Usa complete_order cuando el cliente confirme. Usa revise_order "
                    "si el cliente quiere cambiar algo. Si confirma, complete_order debe "
                    "llevar al nodo final, que dará las gracias y se despedirá."
                ),
            }
        ],
        functions=[complete_order, revise_order, return_to_main_menu],
    )
