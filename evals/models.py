"""Modelos Pydantic para validar escenarios textuales de evaluación.

Pipecat Evals ejecuta las conversaciones. Estos modelos comprueban antes que
los ficheros YAML tienen la estructura esperada y fallan con mensajes claros.
"""

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Modelo base que rechaza campos desconocidos y posibles erratas."""

    model_config = ConfigDict(extra="forbid")


class ExpectedFunctionCall(StrictModel):
    """Herramienta y argumentos que debería seleccionar el agente."""

    name: str = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)


class FunctionCallExpectation(StrictModel):
    """Expectativa determinista sobre una o varias llamadas a herramientas."""

    event: Literal["function_call"]
    calls: list[ExpectedFunctionCall] = Field(min_length=1)


class ResponseExpectation(StrictModel):
    """Criterio semántico usado para juzgar una respuesta del asistente."""

    event: Literal["response"]
    eval: str = Field(min_length=1)


Expectation = Annotated[
    FunctionCallExpectation | ResponseExpectation,
    Field(discriminator="event"),
]


class EvaluationTurn(StrictModel):
    """Intervención del usuario y comportamiento esperado del agente."""

    user: str = Field(min_length=1)
    expect: list[Expectation] = Field(min_length=1)


class EvaluationScenario(StrictModel):
    """Conversación completa que evalúa un recorrido del agente."""

    name: str = Field(min_length=1)
    turns: list[EvaluationTurn] = Field(min_length=1)


class EvaluationSuite(StrictModel):
    """Conjunto de escenarios relacionados y almacenados en un YAML."""

    name: str = Field(min_length=1)
    scenarios: list[EvaluationScenario] = Field(min_length=1)

    @model_validator(mode="after")
    def scenario_names_are_unique(self) -> "EvaluationSuite":
        names = [scenario.name for scenario in self.scenarios]
        if len(names) != len(set(names)):
            raise ValueError("Los nombres de escenario no pueden repetirse.")
        return self


def load_evaluation_suite(path: str | Path) -> EvaluationSuite:
    """Carga un YAML de evaluación y valida toda su estructura."""
    source = Path(path)
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    return EvaluationSuite.model_validate(data)
