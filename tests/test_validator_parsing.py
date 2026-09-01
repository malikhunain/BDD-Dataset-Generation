from validation.output_parsing import parse_behave_output


def test_passing_behave_output():
    output = """
1 feature passed, 0 failed, 0 skipped
5 scenarios passed, 0 failed, 0 skipped
15 steps passed, 0 failed, 0 skipped
"""

    result = parse_behave_output(output, returncode=0)

    assert result.status == "PASS"
    assert result.scenarios_passed == 5
    assert result.scenarios_failed == 0
    assert result.scenarios_total == 5
    assert result.steps_passed == 15
    assert result.steps_failed == 0
    assert result.steps_total == 15
    assert result.pass_rate == 1.0
    assert result.step_pass_rate == 1.0


def test_failing_behave_output():
    output = """
Failing scenarios:
features/example.feature:10 Scenario

0 features passed, 1 failed, 0 skipped
0 scenarios passed, 1 failed, 0 skipped
0 steps passed, 3 failed, 0 skipped
"""

    result = parse_behave_output(output, returncode=1)

    assert result.status == "FAIL_BEHAVE"
    assert result.scenarios_passed == 0
    assert result.scenarios_failed == 1
    assert result.scenarios_total == 1
    assert result.steps_failed == 3
    assert result.failing_scenarios == [
        "features/example.feature:10 Scenario"
    ]


def test_import_error_is_treated_as_syntax_failure():
    output = """
ImportError: No module named 'foo'
"""

    result = parse_behave_output(output, returncode=1)

    assert result.status == "FAIL_SYNTAX"
    assert "ImportError" in result.error_message


def test_attribute_error_is_treated_as_syntax_failure():
    output = """
AttributeError: module 'solution' has no attribute 'wrong_function'
"""

    result = parse_behave_output(output, returncode=1)

    assert result.status == "FAIL_SYNTAX"
    assert "AttributeError" in result.error_message


def test_undefined_steps_are_treated_as_syntax_failure():
    output = """
You can implement step definitions for undefined steps with these snippets:

@given(u'some undefined step')
def step_impl(context):
    raise NotImplementedError('STEP VERSION NOT IMPLEMENTED')
"""

    result = parse_behave_output(output, returncode=1)

    assert result.status == "FAIL_SYNTAX"
    assert "undefined steps" in result.error_message
