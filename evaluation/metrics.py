"""Métricas de transcripción: normalización, alineación, WER y CER.

Implementación propia (sin dependencias) para poder imprimir la alineación
palabra a palabra y contar sustituciones, deleciones e inserciones.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

# Política de normalización: se aplica igual a referencia e hipótesis.
# «un», «una» y «uno» no se convierten: casi siempre son artículos («una mesa»).
NUMBER_WORDS = {
    "dos": "2", "tres": "3", "cuatro": "4", "cinco": "5", "seis": "6",
    "siete": "7", "ocho": "8", "nueve": "9", "diez": "10", "once": "11",
    "doce": "12", "trece": "13", "catorce": "14", "quince": "15",
    "dieciséis": "16", "diecisiete": "17", "dieciocho": "18",
    "diecinueve": "19", "veinte": "20",
}

Operation = Literal["ok", "S", "D", "I"]


@dataclass(frozen=True)
class AlignedWord:
    """Una posición de la alineación entre referencia e hipótesis."""

    op: Operation
    reference: str | None
    hypothesis: str | None


@dataclass(frozen=True)
class ErrorCounts:
    """Errores de una comparación; N son las palabras de la referencia."""

    substitutions: int
    deletions: int
    insertions: int
    reference_words: int

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    @property
    def wer(self) -> float:
        if self.reference_words == 0:
            return 0.0 if self.errors == 0 else float("inf")
        return self.errors / self.reference_words


def normalize_text(text: str) -> str:
    """Minúsculas, sin signos de puntuación y con números en cifras.

    Conserva los dos puntos de las horas («21:00») porque forman un único dato.
    """
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"(?<!\d):|:(?!\d)", " ", text)
    text = re.sub(r"[^\w\s:]", " ", text)
    words = [NUMBER_WORDS.get(word, word) for word in text.split()]
    return " ".join(words)


def tokenize(text: str, *, normalize: bool = True) -> list[str]:
    """Divide en palabras; sin normalizar, «Quiero» y «quiero» son distintas."""
    return (normalize_text(text) if normalize else text).split()


def align(reference: list[str], hypothesis: list[str]) -> list[AlignedWord]:
    """Alineación de distancia mínima (Levenshtein) entre dos secuencias."""
    rows, cols = len(reference) + 1, len(hypothesis) + 1
    cost = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        cost[i][0] = i
    for j in range(cols):
        cost[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            same = reference[i - 1] == hypothesis[j - 1]
            cost[i][j] = min(
                cost[i - 1][j - 1] + (0 if same else 1),
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
            )

    aligned: list[AlignedWord] = []
    i, j = len(reference), len(hypothesis)
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            same = reference[i - 1] == hypothesis[j - 1]
            if cost[i][j] == cost[i - 1][j - 1] + (0 if same else 1):
                op: Operation = "ok" if same else "S"
                aligned.append(AlignedWord(op, reference[i - 1], hypothesis[j - 1]))
                i, j = i - 1, j - 1
                continue
        if i > 0 and cost[i][j] == cost[i - 1][j] + 1:
            aligned.append(AlignedWord("D", reference[i - 1], None))
            i -= 1
        else:
            aligned.append(AlignedWord("I", None, hypothesis[j - 1]))
            j -= 1
    return aligned[::-1]


def count_errors(reference: list[str], hypothesis: list[str]) -> ErrorCounts:
    """Cuenta S, D e I a partir de la alineación."""
    ops = [word.op for word in align(reference, hypothesis)]
    return ErrorCounts(
        substitutions=ops.count("S"),
        deletions=ops.count("D"),
        insertions=ops.count("I"),
        reference_words=len(reference),
    )


def word_errors(reference: str, hypothesis: str, *, normalize: bool = True) -> ErrorCounts:
    """S, D, I y N de una transcripción frente a su referencia."""
    return count_errors(
        tokenize(reference, normalize=normalize),
        tokenize(hypothesis, normalize=normalize),
    )


def wer(reference: str, hypothesis: str, *, normalize: bool = True) -> float:
    """WER = (S + D + I) / N. Puede superar 1 si hay muchas inserciones."""
    return word_errors(reference, hypothesis, normalize=normalize).wer


def cer(reference: str, hypothesis: str, *, normalize: bool = True) -> float:
    """Igual que WER, pero sobre caracteres (sin contar espacios)."""
    ref = (normalize_text(reference) if normalize else reference).replace(" ", "")
    hyp = (normalize_text(hypothesis) if normalize else hypothesis).replace(" ", "")
    return count_errors(list(ref), list(hyp)).wer


def corpus_wer(pairs: list[tuple[str, str]], *, normalize: bool = True) -> float:
    """Suma S, D e I de todos los clips y divide por todas sus palabras."""
    counts = [word_errors(ref, hyp, normalize=normalize) for ref, hyp in pairs]
    total_words = sum(count.reference_words for count in counts)
    total_errors = sum(count.errors for count in counts)
    return total_errors / total_words if total_words else 0.0


def format_alignment(reference: str, hypothesis: str, *, normalize: bool = True) -> str:
    """Tres líneas (REF, HYP y operación) con columnas alineadas."""
    aligned = align(
        tokenize(reference, normalize=normalize),
        tokenize(hypothesis, normalize=normalize),
    )
    columns = [
        (word.reference or "*", word.hypothesis or "*", "" if word.op == "ok" else word.op)
        for word in aligned
    ]
    widths = [max(len(ref), len(hyp), len(op)) for ref, hyp, op in columns]
    lines = []
    for label, index in (("REF", 0), ("HYP", 1), ("   ", 2)):
        cells = [column[index].ljust(width) for column, width in zip(columns, widths)]
        lines.append((f"{label}  " + " ".join(cells)).rstrip())
    return "\n".join(lines)
