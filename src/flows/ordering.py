"""Flujo de pedido de comida con funciones directas de Pipecat Flows."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import NotRequired, TypedDict

from pipecat.flows import FlowManager
from pipecat.flows.types import TRANSITION_IN_YAML

from services.menu import MENU, format_euros
from services.speech_format import format_euros_for_speech, format_phone_for_speech
from services.validation import normalize_address, normalize_name, normalize_phone


class OrderItem(TypedDict):
    """Línea individual del pedido almacenada en el estado del flujo."""

    item_key: str
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
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
    total_spoken: str
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


def order_total(items: list[OrderItem]) -> Decimal:
    """Calcula el total actual del pedido."""
    return sum((item["line_total"] for item in items), start=Decimal("0.00")).quantize(
        Decimal("0.01")
    )


def public_total(items: list[OrderItem]) -> float:
    """Convierte el total exacto a un valor serializable para la herramienta."""
    return float(order_total(items))


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
    line_total = (menu_item["price"] * quantity).quantize(Decimal("0.01"))
    return {
        "item_key": item_key,
        "name": menu_item["name"],
        "quantity": quantity,
        "unit_price": menu_item["price"],
        "line_total": line_total,
        "notes": notes.strip(),
    }


def merge_order_item(items: list[OrderItem], new_item: OrderItem) -> None:
    """Acumula líneas equivalentes para evitar duplicados ambiguos."""
    for item in items:
        if item["item_key"] == new_item["item_key"] and item["notes"] == new_item["notes"]:
            item["quantity"] += new_item["quantity"]
            item["line_total"] = (item["unit_price"] * item["quantity"]).quantize(
                Decimal("0.01")
            )
            return
    items.append(new_item)


def validate_menu_request(item_key: str, quantity: int) -> str | None:
    """Devuelve un mensaje de error si la línea de pedido no es válida."""
    if item_key not in MENU:
        return f"Clave de producto desconocida: {item_key}."
    if quantity < 1 or quantity > 10:
        return "La cantidad debe estar entre 1 y 10."
    return None


def build_order_result(
    status: str,
    items: list[OrderItem],
    *,
    summary: str | None = None,
    **details: str,
) -> OrderResult:
    """Crea la fotografía del pedido que recibe el asistente tras cada acción."""
    result: OrderResult = {
        "status": status,
        "order_summary": summary if summary is not None else summarize_order(items),
        "total": public_total(items),
        "total_text": format_euros(order_total(items)),
        "total_spoken": format_euros_for_speech(order_total(items)),
    }
    result.update(details)
    return result


async def add_menu_item(
    flow_manager: FlowManager, item_key: str, quantity: int, notes: str = ""
) -> tuple[OrderResult, object]:
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
        return build_order_result(
            "error",
            flow_manager.state["order_items"],
            summary=f"{validation_error} Pide al cliente que lo repita.",
        ), TRANSITION_IN_YAML

    merge_order_item(
        flow_manager.state["order_items"], build_order_item(item_key, quantity, notes)
    )

    return build_order_result(
        "añadido", flow_manager.state["order_items"]
    ), TRANSITION_IN_YAML


async def add_multiple_menu_items(
    flow_manager: FlowManager, items: list[MenuItemRequest]
) -> tuple[OrderResult, object]:
    """
    Añade varios productos al pedido actual con una sola llamada de herramienta.

    Args:
        items: Lista de productos. Cada elemento debe incluir item_key y quantity.
            notes es opcional para indicar detalles como sin cebolla.
    """
    ensure_order_state(flow_manager)

    if not items:
        return build_order_result(
            "error",
            flow_manager.state["order_items"],
            summary="No se ha recibido ningún producto para añadir.",
        ), TRANSITION_IN_YAML

    new_items: list[OrderItem] = []
    for request in items:
        item_key = request["item_key"]
        quantity = request["quantity"]
        validation_error = validate_menu_request(item_key, quantity)
        if validation_error:
            return build_order_result(
                "error",
                flow_manager.state["order_items"],
                summary=(
                    f"{validation_error} No he añadido ningún producto del lote. "
                    "Pide al cliente que confirme de nuevo el pedido."
                ),
            ), TRANSITION_IN_YAML

        new_items.append(build_order_item(item_key, quantity, request.get("notes", "")))

    for new_item in new_items:
        merge_order_item(flow_manager.state["order_items"], new_item)

    return build_order_result(
        "añadidos", flow_manager.state["order_items"]
    ), TRANSITION_IN_YAML


async def remove_menu_item(
    flow_manager: FlowManager, item_key: str
) -> tuple[OrderResult, object]:
    """
    Elimina un producto del menú del pedido actual.

    Args:
        item_key: Clave del producto que el cliente quiere eliminar.
    """
    ensure_order_state(flow_manager)

    removed = False
    remaining_items: list[OrderItem] = []
    for item in flow_manager.state["order_items"]:
        if not removed and item["item_key"] == item_key:
            removed = True
            continue
        remaining_items.append(item)
    flow_manager.state["order_items"] = remaining_items

    status = "eliminado" if removed else "no_encontrado"
    return build_order_result(
        status, flow_manager.state["order_items"]
    ), TRANSITION_IN_YAML


async def prepare_checkout(
    flow_manager: FlowManager,
    customer_name: str,
    phone_number: str,
    order_type: str,
    delivery_address: str = "",
) -> tuple[OrderResult, object]:
    """
    Pasa a la confirmación cuando el cliente está listo para terminar.

    Args:
        customer_name: Nombre del cliente para el pedido.
        phone_number: Teléfono de contacto para el pedido.
        order_type: Tipo de pedido: recogida o entrega.
        delivery_address: Dirección de entrega. Obligatoria si order_type es entrega.
    """
    ensure_order_state(flow_manager)
    normalized_name = normalize_name(customer_name)
    normalized_phone = normalize_phone(phone_number)
    flow_manager.state["customer_name"] = normalized_name
    flow_manager.state["order_phone"] = normalized_phone
    requested_order_type = order_type.strip().lower()
    if requested_order_type in {
        "entrega", "domicilio", "a domicilio", "para llevar", "llevar",
    }:
        flow_manager.state["order_type"] = "entrega"
        flow_manager.state["delivery_address"] = normalize_address(delivery_address)
    else:
        flow_manager.state["order_type"] = "recogida"
        flow_manager.state["delivery_address"] = None

    if not flow_manager.state["order_items"]:
        return build_order_result(
            "pedido_vacio",
            flow_manager.state["order_items"],
            summary="El cliente todavía no ha pedido ningún producto.",
        ), TRANSITION_IN_YAML

    if not flow_manager.state["customer_name"]:
        return build_order_result(
            "nombre_no_valido",
            flow_manager.state["order_items"],
            summary="Falta un nombre válido para el pedido.",
        ), TRANSITION_IN_YAML

    if not flow_manager.state["order_phone"]:
        return build_order_result(
            "falta_telefono",
            flow_manager.state["order_items"],
            summary="Falta el teléfono de contacto del cliente.",
        ), TRANSITION_IN_YAML

    if flow_manager.state["order_type"] == "entrega" and not flow_manager.state["delivery_address"]:
        return build_order_result(
            "falta_direccion",
            flow_manager.state["order_items"],
            summary="Falta la dirección de entrega del cliente.",
        ), TRANSITION_IN_YAML

    return build_order_result(
        "listo_para_confirmar",
        flow_manager.state["order_items"],
        customer_name=flow_manager.state["customer_name"],
        phone_number=flow_manager.state["order_phone"],
        phone_spoken=format_phone_for_speech(flow_manager.state["order_phone"]),
        order_type=flow_manager.state["order_type"],
        delivery_address=flow_manager.state["delivery_address"] or "",
    ), TRANSITION_IN_YAML


async def complete_order(flow_manager: FlowManager) -> tuple[OrderResult, object]:
    """
    Completa el pedido cuando el cliente confirma que todos los datos son correctos.
    """
    ensure_order_state(flow_manager)

    return build_order_result(
        "completado",
        flow_manager.state["order_items"],
        customer_name=flow_manager.state["customer_name"] or "",
        phone_number=flow_manager.state["order_phone"] or "",
        phone_spoken=format_phone_for_speech(flow_manager.state["order_phone"] or ""),
        order_type=flow_manager.state["order_type"],
        delivery_address=flow_manager.state["delivery_address"] or "",
    ), TRANSITION_IN_YAML


async def get_order_time_estimate(
    flow_manager: FlowManager,
) -> tuple[DeliveryEstimateResult, object]:
    """Proporciona la estimación actual de recogida o entrega."""
    ensure_order_state(flow_manager)
    minutes = 45 if flow_manager.state["order_type"] == "entrega" else 20
    estimated_time = datetime.now() + timedelta(minutes=minutes)
    return {
        "estimated_time": estimated_time.strftime("%H:%M"),
    }, TRANSITION_IN_YAML
