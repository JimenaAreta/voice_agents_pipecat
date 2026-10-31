import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from p03_ratings import EXAMPLE_CSV, load_ratings, make_dataset
from schemas import LISTENING_TEXTS, Rating

EVALUACION = Path(__file__).parent.parent


def row(**overrides) -> dict[str, str]:
    base = {
        "evaluador": "Evaluador 1", "texto": "reserva", "etiqueta": "A",
        "naturalidad": "4", "datos_correctos": "3", "observacion": "Clara",
    }
    return {**base, **overrides}


def test_csv_strings_are_converted_without_disabling_strict():
    assert Rating.model_validate_strings(row()).naturalidad == 4
    with pytest.raises(ValidationError):
        Rating.model_validate(row())


@pytest.mark.parametrize(
    "overrides",
    [
        {"naturalidad": "7"},
        {"etiqueta": "C"},
        {"texto": "codigo_importe", "datos_correctos": "3"},
        {"observacion": ""},
    ],
)
def test_invalid_ratings_are_rejected(overrides):
    with pytest.raises(ValidationError):
        Rating.model_validate_strings(row(**overrides))


def test_example_csv_reproduces_the_debrief():
    ratings, errors = load_ratings(EXAMPLE_CSV)
    assert not errors
    report = make_dataset(ratings).evaluate_sync(lambda votes: votes, progress=False)
    scores = {case.name: case.scores for case in report.cases}
    assert scores["voz_A"]["Naturalness"].value == pytest.approx(4.0)
    assert scores["voz_B"]["Naturalness"].value == pytest.approx(11 / 3)
    assert scores["voz_A"]["CompleteData"].value == pytest.approx(5 / 6)
    assert scores["voz_B"]["CompleteData"].value == pytest.approx(1.0)


def test_invalid_csv_reports_every_bad_line():
    _, errors = load_ratings(EVALUACION / "data" / "valoraciones_invalidas.csv")
    assert [error.split(",")[0] for error in errors] == ["línea 2", "línea 3", "línea 4"]


def test_listening_page_uses_the_same_texts_as_the_schema():
    html = (EVALUACION / "escucha.html").read_text(encoding="utf-8")
    block = re.search(r"const TEXTS = (\[.*?\]);", html, re.DOTALL).group(1)
    as_json = re.sub(r"(\w+):", r'"\1":', block)
    as_json = re.sub(r",\s*([\]}])", r"\1", as_json)
    page_texts = {item["id"]: (item["text"], tuple(item["fields"])) for item in json.loads(as_json)}
    assert page_texts == LISTENING_TEXTS
