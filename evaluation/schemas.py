"""Contratos de datos de las prácticas.

Los nombres de campo de `Slots` coinciden con los del agente (`src/flows/reservations.py`).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Slots(BaseModel):
    """Datos de una reserva extraídos de una transcripción."""

    model_config = ConfigDict(strict=True, extra="forbid")

    reservation_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    party_size: int = Field(ge=1, le=12)
    reservation_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


# Textos de la escucha y campos que el evaluador debe recuperar al oírlos.
# escucha.html usa los mismos identificadores.
LISTENING_TEXTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "reserva": (
        "Cuatro personas, viernes, veintiuna horas.",
        ("comensales", "día", "hora"),
    ),
    "codigo_importe": (
        "B siete K dos. Treinta y cinco euros con cincuenta céntimos.",
        ("código", "importe"),
    ),
    "pregunta_alternativa": (
        "¿Interior o terraza? Puede cambiar la hora antes de confirmar.",
        ("entonación de pregunta", "opción"),
    ),
}

TextId = Literal["reserva", "codigo_importe", "pregunta_alternativa"]


class Rating(BaseModel):
    """Una valoración de escucha: una etiqueta (A/B) de un texto por un evaluador."""

    model_config = ConfigDict(strict=True, extra="forbid")

    evaluador: str = Field(min_length=1)
    texto: TextId
    etiqueta: Literal["A", "B"]
    naturalidad: int = Field(ge=1, le=5)
    datos_correctos: int = Field(ge=0, le=3)
    observacion: str = Field(min_length=1)

    @model_validator(mode="after")
    def fields_fit_the_text(self) -> "Rating":
        available = len(LISTENING_TEXTS[self.texto][1])
        if self.datos_correctos > available:
            raise ValueError(
                f"datos_correctos={self.datos_correctos}, pero «{self.texto}» solo tiene {available} campos"
            )
        return self

    @property
    def all_fields_correct(self) -> bool:
        return self.datos_correctos == len(LISTENING_TEXTS[self.texto][1])
