"""Soluciones de los casos que se añaden a `p02_agent.py` (no repartir).

    python p02_solucion.py           # los cuatro casos de p02 más C05 y C06
    python p02_solucion.py --fixed   # guiones corregidos

Práctica 2, C05: el agente hace bien la reserva, pero el JSON con los datos
finales llega cortado. Fallan SchemaValid, SlotsCorrect y
ConfirmationSupported; pasan CorrectRecovery y VerifiedCompletion, porque el
backend sí tiene la reserva. Un backend correcto no arregla un contrato roto:
lo que lea ese JSON (un CRM, un SMS de confirmación) se queda sin datos.

Práctica 4, C06: el 16/10 a las 21:00 no hay mesa y el cliente no acepta
ninguna alternativa. Lo correcto es NO reservar (`completed=False`).
Con fallos, el agente dice «confirmada» sin llamar a `confirm_reservation`:
fallan ConfirmationSupported y CorrectRecovery. VerifiedCompletion pasa,
porque no hay ninguna fila, que es lo esperado: el fallo está en lo que dice.
"""

import argparse

from p02_agent import (
    CASE_SPECS,
    CONTACT,
    CaseSpec,
    Expected,
    Say,
    Script,
    Tool,
    print_decision,
    run,
    slots_json,
)
from schemas import Slots

# --- Práctica 2: JSON de datos finales inválido ----------------------------------

C05_STEPS = [
    Tool("start_table_reservation", {
        "reservation_date": "2026-10-14", "party_size": 4, "requested_time": "21:00",
    }),
    Say("Hay mesa. ¿A nombre de quién?"),
    Tool("confirm_reservation", CONTACT),
    Say("Reserva confirmada para cuatro el miércoles a las nueve.", claims_confirmation=True),
]
C05 = CaseSpec(
    name="C05_json_invalido",
    user_turns=[
        "Mesa el 14 de octubre para cuatro a las nueve de la noche.",
        "Ana López, 612 345 678.",
    ],
    expected=Expected(slots=Slots(reservation_date="2026-10-14", party_size=4, reservation_time="21:00")),
    buggy=Script(
        steps=C05_STEPS,
        # Falta la llave de cierre: la salida se cortó.
        slots_json='{"reservation_date": "2026-10-14", "party_size": 4, "reservation_time": "21:00"',
    ),
    fixed=Script(steps=C05_STEPS, slots_json=slots_json("2026-10-14", 4, "21:00")),
)

# --- Práctica 4: recuperación correcta sin reserva ------------------------------

C06_START = [
    Tool("start_table_reservation", {
        "reservation_date": "2026-10-16", "party_size": 4, "requested_time": "21:00",
    }),
]
C06 = CaseSpec(
    name="C06_sin_mesa_no_reserva",
    user_turns=[
        "Mesa el viernes 16 para cuatro a las nueve de la noche.",
        "Entonces nada, gracias.",
    ],
    expected=Expected(
        slots=Slots(reservation_date="2026-10-16", party_size=4, reservation_time="21:00"),
        completed=False,
    ),
    buggy=Script(
        steps=[
            *C06_START,
            Say("Perfecto, le confirmo la reserva para las nueve.", claims_confirmation=True),
        ],
        slots_json=slots_json("2026-10-16", 4, "21:00"),
    ),
    fixed=Script(
        steps=[
            *C06_START,
            Say("A las nueve no hay mesa. Tengo a las seis, a las ocho o a las diez."),
            Say("De acuerdo, no hago la reserva. ¡Hasta pronto!"),
        ],
        # Lo que pidió el cliente, no lo reservado: no hay reserva.
        slots_json=slots_json("2026-10-16", 4, "21:00"),
    ),
)

SOLUTION_SPECS = [*CASE_SPECS, C05, C06]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixed", action="store_true", help="usa los guiones corregidos")
    args = parser.parse_args()

    report = run(args.fixed, specs=SOLUTION_SPECS)
    report.print(include_reasons=True, include_durations=False)
    print_decision(report)


if __name__ == "__main__":
    main()
