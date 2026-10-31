"""Práctica 2: suite de reservas con Pydantic Evals contra el backend real.

Lo único simulado es el LLM: cada caso tiene un guion con las herramientas que
llama, sus argumentos y lo que dice al cliente. Las herramientas son los
handlers reales de `src/flows/reservations.py` y el backend es SQLite (una base
temporal por caso). Así la evidencia del backend no es inventada.

Cada llamada a una herramienta queda registrada con Logfire como un paso
(span) de la traza, y algunos evaluadores leen esa traza. Sin cuenta funciona
en local; con `LOGFIRE_TOKEN` la traza se ve también en Logfire.

    python p02_agent.py           # guiones con los fallos del agente
    python p02_agent.py --fixed   # guiones corregidos

Ejercicio: añade un caso cuyo `slots_json` no sea JSON válido y comprueba qué
evaluadores lo detectan.
"""

import argparse
import asyncio
import os
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import logfire
from loguru import logger
from pydantic import BaseModel, ValidationError
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext, HasMatchingSpan
from pydantic_evals.otel import SpanQuery

from schemas import Slots

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import flows.reservations as reservations  # noqa: E402

logger.disable("flows")
# Sin token no envía nada: la traza solo la leen los evaluadores.
logfire.configure(send_to_logfire="if-token-present", console=False)

TOOLS = {
    "start_table_reservation": reservations.start_table_reservation,
    "collect_party_size": reservations.collect_party_size,
    "check_reservation_availability": reservations.check_reservation_availability,
    "confirm_reservation": reservations.confirm_reservation,
}
CONFIRMED = "reserva_confirmada"


# --- Guiones del LLM simulado -------------------------------------------------

@dataclass
class Tool:
    """El LLM llama a una herramienta real."""

    name: str
    args: dict


@dataclass
class Say:
    """El LLM habla. `claims_confirmation` marca si afirma que la reserva está hecha.

    En una sesión real lo decidiría una regla o un LLMJudge sobre el texto.
    """

    text: str
    claims_confirmation: bool = False


@dataclass
class Script:
    steps: list[Tool | Say]
    # Datos finales que el agente comunica al cliente, en JSON.
    slots_json: str
    # Simula una respuesta perdida: el primer guardado escribe y después falla.
    fail_first_save: bool = False


class CaseInput(BaseModel):
    user_turns: list[str]
    script: Script


# --- Salida de la sesión y expectativa --------------------------------------

class ToolEvent(BaseModel):
    kind: Literal["tool"] = "tool"
    name: str
    args: dict
    status: str


class AgentEvent(BaseModel):
    kind: Literal["agent"] = "agent"
    text: str
    claims_confirmation: bool


class BackendRow(BaseModel):
    reservation_date: str
    party_size: int
    reservation_time: str


class Session(BaseModel):
    events: list[ToolEvent | AgentEvent]
    slots_json: str
    backend_rows: list[BackendRow]


class Expected(BaseModel):
    slots: Slots
    # True si al final debe existir exactamente una reserva con esos datos.
    completed: bool = True


# --- Función bajo prueba ------------------------------------------------------

class FakeFlowManager:
    def __init__(self):
        self.state = {}


def read_backend(db_path: Path) -> list[BackendRow]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT reservation_date, party_size, reservation_time FROM reservations"
        ).fetchall()
    return [BackendRow(reservation_date=d, party_size=p, reservation_time=t) for d, p, t in rows]


def fail_once_after_writing(save):
    """El guardado se completa, pero la herramienta recibe un error (timeout)."""
    calls = {"count": 0}

    def wrapper(reservation_id, details):
        save(reservation_id, details)
        calls["count"] += 1
        if calls["count"] == 1:
            raise sqlite3.OperationalError("timeout simulado tras escribir")

    return wrapper


async def replay(case_input: CaseInput) -> Session:
    script = case_input.script
    flow_manager = FakeFlowManager()
    events: list[ToolEvent | AgentEvent] = []
    original_save = reservations.save_reservation
    original_db_path = os.environ.get("RESERVATIONS_DB_PATH")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "reservations.sqlite3"
        os.environ["RESERVATIONS_DB_PATH"] = str(db_path)
        if script.fail_first_save:
            reservations.save_reservation = fail_once_after_writing(original_save)
        try:
            for step in script.steps:
                if isinstance(step, Tool):
                    with logfire.span("herramienta {tool}", tool=step.name, args=step.args) as span:
                        result, _ = await TOOLS[step.name](flow_manager, **step.args)
                        span.set_attribute("status", result["status"])
                    events.append(ToolEvent(name=step.name, args=step.args, status=result["status"]))
                else:
                    events.append(AgentEvent(text=step.text, claims_confirmation=step.claims_confirmation))
        finally:
            reservations.save_reservation = original_save
            if original_db_path is None:
                os.environ.pop("RESERVATIONS_DB_PATH", None)
            else:
                os.environ["RESERVATIONS_DB_PATH"] = original_db_path
        backend_rows = read_backend(db_path) if db_path.exists() else []
    return Session(events=events, slots_json=script.slots_json, backend_rows=backend_rows)


# --- Evaluadores ---------------------------------------------------------------

def parse_slots(slots_json: str) -> tuple[Slots | None, str | None]:
    try:
        return Slots.model_validate_json(slots_json), None
    except ValidationError as error:
        return None, "; ".join(
            f"{'.'.join(map(str, e['loc'])) or 'json'}: {e['msg']}" for e in error.errors()
        )


def as_row(slots: Slots) -> BackendRow:
    return BackendRow(**slots.model_dump())


@dataclass
class SchemaValid(Evaluator[CaseInput, Session]):
    """Puerta 1: el JSON de datos finales cumple el contrato."""

    def evaluate(self, ctx: EvaluatorContext[CaseInput, Session]) -> EvaluationReason:
        _, error = parse_slots(ctx.output.slots_json)
        return EvaluationReason(value=error is None, reason=error)


@dataclass
class SlotsCorrect(Evaluator[CaseInput, Session]):
    """Puerta 2: lo que el agente comunica coincide con lo que pidió el usuario."""

    def evaluate(self, ctx: EvaluatorContext[CaseInput, Session]) -> EvaluationReason:
        slots, _ = parse_slots(ctx.output.slots_json)
        if slots is None:
            return EvaluationReason(value=False, reason="no hay datos válidos")
        expected = ctx.expected_output.slots.model_dump()
        wrong = [
            f"{key}: esperado {expected[key]!r}, comunicado {value!r}"
            for key, value in slots.model_dump().items()
            if expected[key] != value
        ]
        return EvaluationReason(value=not wrong, reason="; ".join(wrong) or None)


@dataclass
class ConfirmationSupported(Evaluator[CaseInput, Session]):
    """Puerta 3: si el agente confirma, el backend tiene esa reserva con esos datos."""

    def evaluate(self, ctx: EvaluatorContext[CaseInput, Session]) -> EvaluationReason:
        if not any(e.kind == "agent" and e.claims_confirmation for e in ctx.output.events):
            return EvaluationReason(value=True, reason="no afirma ninguna confirmación")
        slots, _ = parse_slots(ctx.output.slots_json)
        if slots is None:
            return EvaluationReason(value=False, reason="confirma sin datos válidos")
        if as_row(slots) in ctx.output.backend_rows:
            return EvaluationReason(value=True)
        found = [row.model_dump() for row in ctx.output.backend_rows] or "sin reservas"
        return EvaluationReason(value=False, reason=f"backend: {found}")


@dataclass
class CorrectRecovery(Evaluator[CaseInput, Session]):
    """Puerta 4: solo confirma después de que la herramienta devuelva éxito."""

    def evaluate(self, ctx: EvaluatorContext[CaseInput, Session]) -> EvaluationReason:
        last_status = None
        for event in ctx.output.events:
            if event.kind == "tool" and event.name == "confirm_reservation":
                last_status = event.status
            elif event.kind == "agent" and event.claims_confirmation and last_status != CONFIRMED:
                return EvaluationReason(
                    value=False,
                    reason=f"afirma confirmación tras {last_status or 'ninguna llamada'}",
                )
        return EvaluationReason(value=True)


@dataclass
class VerifiedCompletion(Evaluator[CaseInput, Session]):
    """Estado final: una sola reserva con los datos esperados (o ninguna)."""

    def evaluate(self, ctx: EvaluatorContext[CaseInput, Session]) -> EvaluationReason:
        rows = ctx.output.backend_rows
        if not ctx.expected_output.completed:
            return EvaluationReason(value=not rows, reason=f"{len(rows)} reservas" if rows else None)
        expected = as_row(ctx.expected_output.slots)
        if rows == [expected]:
            return EvaluationReason(value=True)
        found = [row.model_dump() for row in rows] or "sin reservas"
        return EvaluationReason(value=False, reason=f"esperado {expected.model_dump()}, backend: {found}")


def called_tool(name: str) -> HasMatchingSpan:
    """Evaluador de traza: algún paso de la sesión llamó a la herramienta `name`."""
    return HasMatchingSpan(
        query=SpanQuery(has_attributes={"tool": name}),
        evaluation_name=f"Llama_{name}",
    )


# --- Casos ---------------------------------------------------------------------
# Calendario de demo: el 14/10/2026 tiene libres todas las horas; el 16/10/2026
# solo 18:00, 20:00 y 22:00 (ver src/services/reservation_store.py).

CONTACT = {"customer_name": "Ana López", "phone_number": "612 345 678"}


def slots_json(date: str, party_size: int, time: str) -> str:
    return Slots(reservation_date=date, party_size=party_size, reservation_time=time).model_dump_json()


@dataclass
class CaseSpec:
    name: str
    user_turns: list[str]
    expected: Expected
    buggy: Script
    fixed: Script | None = None  # None: el guion ya es correcto
    # Evaluadores solo de este caso, además de los cinco comunes.
    evaluators: list[Evaluator] = field(default_factory=list)


C01 = CaseSpec(
    name="C01_reserva_basica",
    user_turns=[
        "Mesa el 14 de octubre para cuatro a las nueve de la noche.",
        "Ana López, 612 345 678.",
    ],
    expected=Expected(slots=Slots(reservation_date="2026-10-14", party_size=4, reservation_time="21:00")),
    buggy=Script(
        steps=[
            Tool("start_table_reservation", {
                "reservation_date": "2026-10-14", "party_size": 4, "requested_time": "21:00",
            }),
            Say("Hay mesa. ¿A nombre de quién?"),
            Tool("confirm_reservation", CONTACT),
            Say("Reserva confirmada para cuatro el miércoles a las nueve.", claims_confirmation=True),
        ],
        slots_json=slots_json("2026-10-14", 4, "21:00"),
    ),
)

C02_CORRECTION = [
    Tool("start_table_reservation", {
        "reservation_date": "2026-10-14", "party_size": 4, "requested_time": "21:00",
    }),
    Say("Hay mesa. ¿A nombre de quién?"),
]
C02 = CaseSpec(
    name="C02_correccion",
    user_turns=[
        "Mesa el 14 de octubre para cuatro a las nueve de la noche.",
        "Perdona, al final seremos cinco. Ana López, 612 345 678.",
    ],
    expected=Expected(slots=Slots(reservation_date="2026-10-14", party_size=5, reservation_time="21:00")),
    buggy=Script(
        steps=[
            *C02_CORRECTION,
            Say("De acuerdo, cinco personas."),  # acepta la corrección, pero no la aplica
            Tool("confirm_reservation", CONTACT),
            Say("Reserva confirmada para cinco a las nueve.", claims_confirmation=True),
        ],
        slots_json=slots_json("2026-10-14", 5, "21:00"),
    ),
    fixed=Script(
        steps=[
            *C02_CORRECTION,
            Tool("collect_party_size", {"party_size": 5}),
            Say("De acuerdo, cinco personas."),
            Tool("confirm_reservation", CONTACT),
            Say("Reserva confirmada para cinco a las nueve.", claims_confirmation=True),
        ],
        slots_json=slots_json("2026-10-14", 5, "21:00"),
    ),
    evaluators=[called_tool("collect_party_size")],
)

C03 = CaseSpec(
    name="C03_alternativa",
    user_turns=[
        "Mesa el viernes 16 para cuatro a las nueve de la noche.",
        "Vale, a las diez.",
        "Ana López, 612 345 678.",
    ],
    expected=Expected(slots=Slots(reservation_date="2026-10-16", party_size=4, reservation_time="22:00")),
    buggy=Script(
        steps=[
            Tool("start_table_reservation", {
                "reservation_date": "2026-10-16", "party_size": 4, "requested_time": "21:00",
            }),
            Say("A las nueve no hay mesa. Tengo a las seis, a las ocho o a las diez."),
            Tool("check_reservation_availability", {"requested_time": "22:00"}),
            Say("A las diez sí. ¿A nombre de quién?"),
            Tool("confirm_reservation", CONTACT),
            Say("Reserva confirmada para cuatro el viernes a las diez.", claims_confirmation=True),
        ],
        slots_json=slots_json("2026-10-16", 4, "22:00"),
    ),
)

C04_START = [
    Tool("start_table_reservation", {
        "reservation_date": "2026-10-14", "party_size": 4, "requested_time": "21:00",
    }),
    Say("Hay mesa. ¿A nombre de quién?"),
    Tool("confirm_reservation", CONTACT),  # devuelve error_guardado
]
C04 = CaseSpec(
    name="C04_timeout",
    user_turns=[
        "Mesa el 14 de octubre para cuatro a las nueve de la noche.",
        "Ana López, 612 345 678.",
        "Sí, inténtalo otra vez.",
    ],
    expected=Expected(slots=Slots(reservation_date="2026-10-14", party_size=4, reservation_time="21:00")),
    buggy=Script(
        steps=[
            *C04_START,
            Say("Confirmada. ¡Hasta el miércoles!", claims_confirmation=True),
        ],
        slots_json=slots_json("2026-10-14", 4, "21:00"),
        fail_first_save=True,
    ),
    fixed=Script(
        steps=[
            *C04_START,
            Say("No he podido guardar la reserva. ¿Quiere que lo intente de nuevo?"),
            Tool("confirm_reservation", CONTACT),  # mismo id: no duplica la reserva
            Say("Ahora sí: reserva confirmada para cuatro a las nueve.", claims_confirmation=True),
        ],
        slots_json=slots_json("2026-10-14", 4, "21:00"),
        fail_first_save=True,
    ),
)

CASE_SPECS = [C01, C02, C03, C04]


def make_dataset(fixed: bool = False, specs: list[CaseSpec] = CASE_SPECS) -> Dataset:
    cases = [
        Case(
            name=spec.name,
            inputs=CaseInput(
                user_turns=spec.user_turns,
                script=(spec.fixed or spec.buggy) if fixed else spec.buggy,
            ),
            expected_output=spec.expected,
            evaluators=tuple(spec.evaluators),
        )
        for spec in specs
    ]
    evaluators = [SchemaValid(), SlotsCorrect(), ConfirmationSupported(), CorrectRecovery(), VerifiedCompletion()]
    return Dataset(name="p02_reservas", cases=cases, evaluators=evaluators)


def run(fixed: bool = False, specs: list[CaseSpec] = CASE_SPECS):
    # Un caso cada vez: cada sesión usa su propia base indicada por variable de entorno.
    return make_dataset(fixed, specs).evaluate_sync(replay, progress=False, max_concurrency=1)


def failed_gates(case) -> list[str]:
    """Evaluadores que fallan en un caso; un evaluador que no pudo ejecutarse también cuenta."""
    failed = [name for name, result in case.assertions.items() if not result.value]
    return failed + [failure.name for failure in case.evaluator_failures]


def print_decision(report) -> None:
    """La puerta del negocio: todos los criterios en todos los casos, no una media."""
    print("\n== Puerta de aceptación ==\n")
    blocked = False
    for case in report.cases:
        failed = failed_gates(case)
        blocked |= bool(failed)
        print(f"{case.name}: {'OK' if not failed else 'FALLA ' + ', '.join(failed)}")
    print(f"\nDecisión: {'BLOQUEAR' if blocked else 'SUPERA LA PUERTA DE AULA (ampliar casos antes de producción)'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixed", action="store_true", help="usa los guiones corregidos")
    args = parser.parse_args()

    print(f"== Suite de reservas ({'--fixed' if args.fixed else 'versión con fallos'}) ==\n")
    report = run(args.fixed)
    report.print(include_reasons=True, include_durations=False)
    print_decision(report)


if __name__ == "__main__":
    main()
