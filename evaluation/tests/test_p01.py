import pytest

from metrics import cer, corpus_wer, normalize_text, wer, word_errors
from p01_schema_stt import CASES, make_dataset, replay_stt


def test_slide_example_one_substitution_is_ten_percent():
    counts = word_errors(
        "quiero una mesa para cuatro el viernes a las nueve",
        "quiero una mesa para cinco el viernes a las nueve",
    )
    assert (counts.substitutions, counts.deletions, counts.insertions) == (1, 0, 0)
    assert counts.wer == pytest.approx(0.10)


def test_insertions_can_push_wer_above_one():
    assert wer("sí", "sí sí sí") == pytest.approx(2.0)


def test_corpus_wer_weights_by_words():
    long_reference = " ".join(f"palabra{i}" for i in range(100))
    long_hypothesis = long_reference.replace("palabra0", "otra", 1)
    pairs = [("para cuatro", "para cinco"), (long_reference, long_hypothesis)]
    mean_per_clip = sum(wer(ref, hyp) for ref, hyp in pairs) / len(pairs)
    assert mean_per_clip == pytest.approx(0.255)
    assert corpus_wer(pairs) == pytest.approx(2 / 102)


def test_normalization_applies_same_policy_to_both_sides():
    assert normalize_text("Quiero una mesa para cuatro, a las 21:00.") == (
        "quiero una mesa para 4 a las 21:00"
    )
    assert wer("Para cuatro.", "para 4", normalize=False) == pytest.approx(1.0)
    assert wer("Para cuatro.", "para 4") == 0.0


def test_cer_counts_characters():
    assert cer("mesa", "misa") == pytest.approx(1 / 4)


def test_same_wer_different_task_impact():
    cases = {case.name: case for case in CASES}
    a, b = cases["A_comensales"], cases["B_articulo"]
    assert wer(a.expected_output.reference, a.inputs) == wer(b.expected_output.reference, b.inputs)
    assert replay_stt(a.inputs).slots.party_size == 5
    assert replay_stt(b.inputs).slots == b.expected_output.slots


def test_missing_time_breaks_the_contract():
    result = replay_stt("Quiero una mesa para 4 el viernes.")
    assert result.slots is None
    assert "reservation_time" in result.schema_error


def test_dataset_runs_without_external_services():
    report = make_dataset().evaluate_sync(replay_stt, progress=False)
    assertions = {
        case.name: {name: result.value for name, result in case.assertions.items()}
        for case in report.cases
    }
    assert assertions["A_comensales"] == {"SchemaValid": True, "SlotsCorrect": False}
    assert assertions["solo_formato"] == {"SchemaValid": True, "SlotsCorrect": True}
    assert assertions["hora_perdida"]["SchemaValid"] is False
