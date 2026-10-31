"""Práctica 3: valoraciones de escucha validadas con Pydantic y resumidas con Evals.

    python p03_ratings.py --csv valoraciones.csv

El CSV sale de escucha.html. Si una fila no cumple el esquema `Rating`, el
fichero se rechaza entero antes de generar el informe.

Naturalidad (1-5) y datos correctos son resultados separados: una voz natural
puede hacer que se pierda un dato.
"""

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext

from schemas import Rating

EXAMPLE_CSV = Path(__file__).parent / "data" / "valoraciones_ejemplo.csv"


def load_ratings(path: Path) -> tuple[list[Rating], list[str]]:
    """Valida cada fila; devuelve las valoraciones y los errores con su línea."""
    ratings, errors = [], []
    with path.open(encoding="utf-8", newline="") as file:
        for line, row in enumerate(csv.DictReader(file), start=2):
            try:
                # Del CSV todo llega como texto: model_validate_strings lo
                # convierte sin desactivar strict ni los rangos.
                ratings.append(Rating.model_validate_strings(row))
            except ValidationError as error:
                for problem in error.errors():
                    location = ".".join(map(str, problem["loc"])) or "fila"
                    errors.append(f"línea {line}, {location}: {problem['msg']}")
    return ratings, errors


@dataclass
class Naturalness(Evaluator[list[Rating], list[Rating]]):
    """Media de naturalidad. Escala ordinal: leerla junto a la distribución."""

    def evaluate(self, ctx: EvaluatorContext[list[Rating], list[Rating]]) -> EvaluationReason:
        values = [rating.naturalidad for rating in ctx.output]
        distribution = Counter(values)
        reason = " ".join(f"{score}:{distribution[score]}" for score in range(1, 6))
        return EvaluationReason(value=sum(values) / len(values), reason=f"distribución {reason}")


@dataclass
class CompleteData(Evaluator[list[Rating], list[Rating]]):
    """Proporción de votos que recuperan todos los campos críticos de su texto."""

    def evaluate(self, ctx: EvaluatorContext[list[Rating], list[Rating]]) -> EvaluationReason:
        complete = sum(rating.all_fields_correct for rating in ctx.output)
        missed = [
            f"{r.texto} ({r.evaluador}): {r.observacion}"
            for r in ctx.output
            if not r.all_fields_correct
        ]
        reason = f"{complete}/{len(ctx.output)} votos"
        if missed:
            reason += " · fallos: " + "; ".join(missed)
        return EvaluationReason(value=complete / len(ctx.output), reason=reason)


def make_dataset(ratings: list[Rating]) -> Dataset:
    cases = [
        Case(name=f"voz_{label}", inputs=[r for r in ratings if r.etiqueta == label])
        for label in ("A", "B")
        if any(r.etiqueta == label for r in ratings)
    ]
    return Dataset(name="p03_escucha", cases=cases, evaluators=[Naturalness(), CompleteData()])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=EXAMPLE_CSV, help="CSV exportado por escucha.html")
    args = parser.parse_args()

    ratings, errors = load_ratings(args.csv)
    if errors:
        print(f"CSV rechazado ({args.csv.name}): {len(errors)} errores\n")
        print("\n".join(errors))
        sys.exit(1)
    if not ratings:
        print("El CSV no tiene valoraciones.")
        sys.exit(1)

    listeners = {rating.evaluador for rating in ratings}
    print(f"{len(ratings)} valoraciones validadas · {len(listeners)} oyentes · {args.csv.name}\n")

    # La "función bajo prueba" ya se ejecutó en la escucha: aquí solo se resumen los votos.
    report = make_dataset(ratings).evaluate_sync(
        lambda votes: votes, progress=False, task_name="escucha"
    )
    report.print(include_reasons=True, include_durations=False)

    print(
        "\nMuestra pequeña: los votos del mismo oyente no son independientes y "
        "una diferencia de medias así no es estadísticamente significativa."
    )


if __name__ == "__main__":
    main()
