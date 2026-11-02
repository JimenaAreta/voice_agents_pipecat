"""Contratos de datos de las prácticas.

Los nombres de campo de `Slots` coinciden con los del agente (`src/flows/reservations.py`).
"""

from pydantic import BaseModel, ConfigDict, Field


class Slots(BaseModel):
    """Datos de una reserva extraídos de una transcripción."""

    model_config = ConfigDict(strict=True, extra="forbid")

    reservation_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    party_size: int = Field(ge=1, le=12)
    reservation_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
