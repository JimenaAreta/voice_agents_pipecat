"""Práctica 1: contrato de datos (Pydantic) y WER (Pydantic Evals).

Cadena evaluada en cada caso:

    hipótesis del STT ─┬─ WER frente a la referencia          (calidad del texto)
                       └─ extract_slots → Slots.model_validate (contrato)
                                        → comparar con los slots esperados (tarea)

Las hipótesis son replays con el formato que devuelve Deepgram con
`smart_format` (cifras, horas «21:00» y puntuación). No se usa audio ni API.

Ejercicio: añade un caso a `CASES` y explica qué detecta cada evaluador.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import BaseModel, ValidationError
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext

from metrics import corpus_wer, format_alignment, normalize_text, wer, word_errors
from schemas import Slots

# Lunes de referencia para resolver «el viernes» sin depender del día real.
REFERENCE_DATE = date(2026, 10, 12)
WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class Expected(BaseModel):
    """Referencia revisada por una persona y datos que debía entenderse."""

    reference: str
    slots: Slots


class STTResult(BaseModel):
    """Salida de la función evaluada."""

    transcript: str
    slots: Slots | None
    schema_error: str | None


def extract_slots(transcript: str) -> dict:
    """Extractor de reglas: sustituye al LLM para que la práctica sea determinista."""
    text = normalize_text(transcript)
    payload: dict = {}
    if match := re.search(r"\bpara (\d+)\b", text):
        payload["party_size"] = int(match.group(1))
    if match := re.search(r"\b(\d{1,2}:\d{2})\b", text):
        payload["reservation_time"] = match.group(1)
    for index, weekday in enumerate(WEEKDAYS):
        if re.search(rf"\b{weekday}\b", text):
            offset = (index - REFERENCE_DATE.weekday()) % 7
            payload["reservation_date"] = (REFERENCE_DATE + timedelta(days=offset)).isoformat()
            break
    return payload


def replay_stt(hypothesis: str) -> STTResult:
    """Función bajo prueba: replay del STT + extracción + validación del contrato."""
    try:
        slots = Slots.model_validate(extract_slots(hypothesis))
        return STTResult(transcript=hypothesis, slots=slots, schema_error=None)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc'])) or 'payload'}: {e['msg']}" for e in error.errors()
        )
        return STTResult(transcript=hypothesis, slots=None, schema_error=problems)


@dataclass
class RawWER(Evaluator[str, STTResult]):
    """WER sin normalizar: mayúsculas, signos y cifras cuentan como errores."""

    def evaluate(self, ctx: EvaluatorContext[str, STTResult]) -> float:
        return wer(ctx.expected_output.reference, ctx.output.transcript, normalize=False)


@dataclass
class WER(Evaluator[str, STTResult]):
    """WER tras aplicar la misma normalización a referencia e hipótesis."""

    def evaluate(self, ctx: EvaluatorContext[str, STTResult]) -> float:
        return wer(ctx.expected_output.reference, ctx.output.transcript)


@dataclass
class SchemaValid(Evaluator[str, STTResult]):
    """¿Los datos extraídos cumplen el contrato? No sabe qué dijo el usuario."""

    def evaluate(self, ctx: EvaluatorContext[str, STTResult]) -> EvaluationReason:
        if ctx.output.schema_error:
            return EvaluationReason(value=False, reason=ctx.output.schema_error)
        return EvaluationReason(value=True)


@dataclass
class SlotsCorrect(Evaluator[str, STTResult]):
    """¿Los datos extraídos coinciden con los que pidió el usuario?"""

    def evaluate(self, ctx: EvaluatorContext[str, STTResult]) -> EvaluationReason:
        if ctx.output.slots is None:
            return EvaluationReason(value=False, reason="no hay slots válidos")
        expected = ctx.expected_output.slots.model_dump()
        obtained = ctx.output.slots.model_dump()
        wrong = [
            f"{field}: esperado {expected[field]!r}, obtenido {obtained[field]!r}"
            for field in expected
            if expected[field] != obtained[field]
        ]
        return EvaluationReason(value=not wrong, reason="; ".join(wrong) or None)


# Referencia escrita con la convención de Deepgram (cifras y horas HH:MM).
REFERENCE = "Quiero una mesa para 4 el viernes a las 21:00."
EXPECTED_SLOTS = Slots(reservation_date="2026-10-16", party_size=4, reservation_time="21:00")


def make_case(name: str, hypothesis: str, reference: str = REFERENCE) -> Case:
    return Case(
        name=name,
        inputs=hypothesis,
        expected_output=Expected(reference=reference, slots=EXPECTED_SLOTS),
    )


CASES = [
    make_case("exacta", REFERENCE),
    # A y B tienen el mismo WER (10 %), pero solo A cambia un dato crítico.
    make_case("A_comensales", "Quiero una mesa para 5 el viernes a las 21:00."),
    make_case("B_articulo", "Quiero la mesa para 4 el viernes a las 21:00."),
    # La persona escribió la referencia en palabras: el error es solo de formato.
    make_case(
        "solo_formato",
        "Quiero una mesa para 4 el viernes a las 21:00.",
        reference="quiero una mesa para cuatro el viernes a las 21:00",
    ),
    # Deleción de «a las 21:00»: falta un campo obligatorio del contrato.
    make_case("hora_perdida", "Quiero una mesa para 4 el viernes."),
]


# Payloads que Pydantic debe rechazar antes de llegar a la evaluación.
REJECTED_PAYLOADS = {
    "comensales como texto": {
        "reservation_date": "2026-10-16", "party_size": "4", "reservation_time": "21:00",
    },
    "campo desconocido": {
        "reservation_date": "2026-10-16", "party_size": 4, "reservation_time": "21:00",
        "terraza": True,
    },
    "fuera de rango": {
        "reservation_date": "2026-10-16", "party_size": 0, "reservation_time": "21:00",
    },
    "hora imposible": {
        "reservation_date": "2026-10-16", "party_size": 4, "reservation_time": "25:00",
    },
}


def show_schema_rejections() -> None:
    print("== 1. Contrato: payloads rechazados por Slots ==\n")
    for label, payload in REJECTED_PAYLOADS.items():
        try:
            Slots.model_validate(payload)
            print(f"[ACEPTADO] {label}")
        except ValidationError as error:
            first = error.errors()[0]
            print(f"[RECHAZADO] {label}: {first['loc'][0]} → {first['msg']}")
    print()


def show_alignments() -> None:
    print("== 2. Alineación normalizada por caso ==\n")
    for case in CASES:
        reference = case.expected_output.reference
        counts = word_errors(reference, case.inputs)
        print(
            f"{case.name}: S={counts.substitutions} D={counts.deletions} "
            f"I={counts.insertions} N={counts.reference_words} → WER {counts.wer:.0%}"
        )
        print(format_alignment(reference, case.inputs), end="\n\n")


def make_dataset() -> Dataset:
    return Dataset(
        name="p01_stt",
        cases=CASES,
        evaluators=[RawWER(), WER(), SchemaValid(), SlotsCorrect()],
    )


def main() -> None:
    show_schema_rejections()
    show_alignments()

    print("== 3. Informe de Pydantic Evals (WER: menor es mejor) ==\n")
    report = make_dataset().evaluate_sync(replay_stt, progress=False)
    report.print(include_reasons=True, include_durations=False)

    print("\n== 4. Agregados: media por clip frente a WER de corpus ==\n")
    pairs = [(case.expected_output.reference, case.inputs) for case in CASES]
    # Un clip corto con un error pesa igual que uno largo en la media por clip.
    short_clip = ("Para 4.", "Para 5.")
    for label, sample in (("casos del dataset", pairs), ("+ clip corto", [*pairs, short_clip])):
        mean_per_clip = sum(wer(ref, hyp) for ref, hyp in sample) / len(sample)
        print(
            f"{label}: media por clip {mean_per_clip:.2%} · "
            f"corpus {corpus_wer(sample):.2%}"
        )


if __name__ == "__main__":
    main()
