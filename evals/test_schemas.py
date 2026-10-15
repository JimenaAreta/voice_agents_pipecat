"""Validación determinista de los escenarios que ejecutará Pipecat Evals."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.models import EvaluationSuite, load_evaluation_suite


EVALS_DIR = Path(__file__).parent


@pytest.mark.parametrize("filename", ["orders.yaml", "reservations.yaml"])
def test_evaluation_yaml_is_valid(filename):
    suite = load_evaluation_suite(EVALS_DIR / filename)
    assert suite.scenarios
    assert all(scenario.turns for scenario in suite.scenarios)


def test_function_call_expectation_requires_at_least_one_call():
    with pytest.raises(ValidationError):
        EvaluationSuite.model_validate(
            {
                "name": "invalid_suite",
                "scenarios": [
                    {
                        "name": "invalid_scenario",
                        "turns": [
                            {
                                "user": "Quiero reservar.",
                                "expect": [
                                    {"event": "function_call", "calls": []},
                                ],
                            }
                        ],
                    }
                ],
            }
        )


def test_unknown_expectation_event_is_rejected():
    with pytest.raises(ValidationError):
        EvaluationSuite.model_validate(
            {
                "name": "invalid_suite",
                "scenarios": [
                    {
                        "name": "invalid_scenario",
                        "turns": [
                            {
                                "user": "Hola.",
                                "expect": [{"event": "unknown"}],
                            }
                        ],
                    }
                ],
            }
        )
