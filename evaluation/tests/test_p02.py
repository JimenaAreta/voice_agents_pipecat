from p02_agent import failed_gates, run


def failed_by_case(report) -> dict[str, list[str]]:
    return {case.name: failed_gates(case) for case in report.cases}


def test_buggy_scripts_fail_the_expected_gates():
    assert failed_by_case(run(fixed=False)) == {
        "C01_reserva_basica": [],
        "C02_correccion": ["Llama_collect_party_size", "ConfirmationSupported", "VerifiedCompletion"],
        "C03_alternativa": [],
        "C04_timeout": ["CorrectRecovery"],
    }


def test_fixed_scripts_pass_every_gate():
    assert all(not failed for failed in failed_by_case(run(fixed=True)).values())


def test_retry_after_lost_response_does_not_duplicate_the_reservation():
    report = run(fixed=True)
    timeout_case = next(case for case in report.cases if case.name == "C04_timeout")
    assert len(timeout_case.output.backend_rows) == 1



def test_solution_cases_fail_the_expected_gates():
    from p02_solucion import C05, C06

    report = run(specs=[C05, C06])
    assert failed_by_case(report) == {
        "C05_json_invalido": ["SchemaValid", "SlotsCorrect", "ConfirmationSupported"],
        "C06_sin_mesa_no_reserva": ["ConfirmationSupported", "CorrectRecovery"],
    }


def test_fixed_solution_cases_pass_and_no_table_means_no_reservation():
    from p02_solucion import C05, C06

    report = run(fixed=True, specs=[C05, C06])
    assert all(not failed for failed in failed_by_case(report).values())
    no_table_case = next(case for case in report.cases if case.name == "C06_sin_mesa_no_reserva")
    assert no_table_case.output.backend_rows == []
