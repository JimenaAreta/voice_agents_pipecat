from decimal import Decimal

import pytest

from flows.ordering import (
    add_menu_item,
    build_order_item,
    merge_order_item,
    order_total,
    prepare_checkout,
    remove_menu_item,
)


class FakeFlowManager:
    def __init__(self):
        self.state = {}


def test_decimal_total_and_duplicate_merge():
    items = []
    merge_order_item(items, build_order_item("tortilla_espanola", 1))
    merge_order_item(items, build_order_item("tortilla_espanola", 2))
    assert len(items) == 1
    assert items[0]["quantity"] == 3
    assert order_total(items) == Decimal("25.50")


@pytest.mark.asyncio
async def test_remove_only_one_matching_line():
    flow = FakeFlowManager()
    await add_menu_item(flow, "tortilla_espanola", 1, "con cebolla")
    await add_menu_item(flow, "tortilla_espanola", 1, "sin cebolla")
    result, _ = await remove_menu_item(flow, "tortilla_espanola")
    assert result["status"] == "eliminado"
    assert len(flow.state["order_items"]) == 1
    assert flow.state["order_items"][0]["notes"] == "sin cebolla"


@pytest.mark.asyncio
async def test_para_llevar_requires_an_address_and_preserves_name():
    flow = FakeFlowManager()
    await add_menu_item(flow, "tortilla_espanola", 1)

    missing, _ = await prepare_checkout(
        flow, "Ana", "612345678", "para llevar"
    )
    assert missing["status"] == "falta_direccion"

    ready, _ = await prepare_checkout(
        flow, "Ana", "612345678", "para llevar", "Calle Mayor 10"
    )
    assert ready["status"] == "listo_para_confirmar"
    assert ready["customer_name"] == "Ana"
    assert ready["delivery_address"] == "Calle Mayor 10"
    assert ready["total_spoken"] == "ocho euros con cincuenta céntimos"
