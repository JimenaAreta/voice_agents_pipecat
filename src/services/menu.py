"""Fixed menu for El Rincón de Castilla.

Keeping the menu in a separate module makes the conversational flow easier to
read. In a real application, this data could come from a database, a CMS, or a
point-of-sale system.
"""

from decimal import Decimal

MENU = {
    "tortilla_espanola": {
        "name": "Tortilla española",
        "category": "entrante",
        "price": Decimal("8.50"),
        "description": "tortilla clásica de patata y cebolla",
    },
    "croquetas_jamon": {
        "name": "Croquetas de jamón",
        "category": "entrante",
        "price": Decimal("9.00"),
        "description": "croquetas cremosas de jamón ibérico",
    },
    "gazpacho_andaluz": {
        "name": "Gazpacho andaluz",
        "category": "entrante",
        "price": Decimal("7.50"),
        "description": "sopa fría de tomate con pepino, pimiento y aceite de oliva",
    },
    "paella_valenciana": {
        "name": "Paella valenciana",
        "category": "principal",
        "price": Decimal("18.50"),
        "description": "arroz con azafrán, pollo, conejo, judía verde y garrofó",
    },
    "pulpo_gallega": {
        "name": "Pulpo a la gallega",
        "category": "principal",
        "price": Decimal("19.00"),
        "description": "pulpo con pimentón, aceite de oliva y patatas",
    },
    "patatas_bravas": {
        "name": "Patatas bravas",
        "category": "guarnición",
        "price": Decimal("6.50"),
        "description": "patatas fritas con salsa brava picante y alioli",
    },
    "crema_catalana": {
        "name": "Crema catalana",
        "category": "postre",
        "price": Decimal("6.50"),
        "description": "postre de crema con azúcar caramelizado",
    },
    "agua_con_gas": {
        "name": "Agua con gas",
        "category": "bebida",
        "price": Decimal("3.00"),
        "description": "agua con gas fría",
    },
    "vino_tinto": {
        "name": "Vino tinto",
        "category": "bebida",
        "price": Decimal("5.00"),
        "description": "copa de vino tinto español",
    },
}


def format_euros(amount: Decimal | float | int) -> str:
    """Formats amounts so the TTS can pronounce them naturally."""
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    return f"{value:.2f}".replace(".", ",") + " euros"


def format_menu_for_prompt() -> str:
    """Returns a compact menu summary for the LLM instructions."""
    return "\n".join(
        f"- {key}: {item['name']} ({format_euros(item['price'])}) - {item['description']}"
        for key, item in MENU.items()
    )
