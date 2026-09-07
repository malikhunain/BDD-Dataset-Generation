"""
Single-problem generation runner.

This module processes one problem end-to-end:

    prompt -> LLM -> parse/write -> validate -> retry if needed
"""

from config import MAX_RETRIES

from bdd_pipeline.records import ProblemRecord
from bdd_pipeline.llm import OllamaClient, OllamaError
from bdd_pipeline.parsing import ParseError, parse_and_write
from bdd_pipeline.prompts import build_prompt
from bdd_pipeline.reporting import Reporter, RunRecord
from bdd_pipeline.validation import ValidationResult, validate

from bdd_pipeline.orchestration.raw_logs import log_raw_response


# Temperature schedule:
#   attempt 0 -> 0.2 for determinism
#   attempt 1 -> 0.7 to escape repeated failures
#   attempt 2 -> 0.9 for maximum variation
_RETRY_TEMPERATURES = (0.2, 0.7, 0.9)


def run_single(
    problem: ProblemRecord,
    client: OllamaClient,
    reporter: Reporter,
) -> RunRecord:
    """
    Process one problem end-to-end.

    Handles retries internally and returns a RunRecord with the final outcome.
    """
    generation_time_total = 0.0

    for retry in range(MAX_RETRIES + 1):
        if retry > 0:
            print(f"    Retry {retry}/{MAX_RETRIES} for {problem.problem_id}...")

        prompt = build_prompt(problem)

        retry_temperature = _RETRY_TEMPERATURES[
            min(retry, len(_RETRY_TEMPERATURES) - 1)
        ]

        if retry > 0:
            original_options = dict(client.options)
            client.options["temperature"] = retry_temperature

        try:
            raw, generation_time = client.generate(prompt)
            generation_time_total += generation_time

        except OllamaError as e:
            print(f"    [FAIL_LLM] {problem.problem_id}: {e}")

            return RunRecord(
                problem_id=problem.problem_id,
                source=problem.source,
                function_name=problem.function_name,
                status="FAIL_LLM",
                scenarios_passed=0,
                scenarios_total=0,
                steps_passed=0,
                steps_total=0,
                scenario_pass_rate=0.0,
                step_pass_rate=0.0,
                generation_time_s=generation_time_total,
                error_message=str(e)[:200],
                retry_count=retry,
            )

        finally:
            if retry > 0:
                client.options = original_options

        log_raw_response(problem, retry, raw)

        try:
            parsed = parse_and_write(problem, raw)

        except ParseError as e:
            if retry < MAX_RETRIES:
                print(
                    f"    [PARSE FAIL] {problem.problem_id}: {e} — retrying..."
                )
                continue

            return RunRecord(
                problem_id=problem.problem_id,
                source=problem.source,
                function_name=problem.function_name,
                status="FAIL_PARSE",
                scenarios_passed=0,
                scenarios_total=0,
                steps_passed=0,
                steps_total=0,
                scenario_pass_rate=0.0,
                step_pass_rate=0.0,
                generation_time_s=generation_time_total,
                error_message=str(e)[:200],
                retry_count=retry,
            )

        validation: ValidationResult = validate(parsed)

        if validation.status == "PASS":
            print(
                f"    [PASS] {problem.problem_id}  "
                f"{validation.scenarios_passed}/{validation.scenarios_total} scenarios  "
                f"({generation_time_total:.1f}s)"
            )

            return RunRecord(
                problem_id=problem.problem_id,
                source=problem.source,
                function_name=problem.function_name,
                status="PASS",
                scenarios_passed=validation.scenarios_passed,
                scenarios_total=validation.scenarios_total,
                steps_passed=validation.steps_passed,
                steps_total=validation.steps_total,
                scenario_pass_rate=validation.pass_rate,
                step_pass_rate=validation.step_pass_rate,
                generation_time_s=generation_time_total,
                error_message="",
                retry_count=retry,
            )

        if retry < MAX_RETRIES:
            print(
                f"    [{validation.status}] {problem.problem_id}: "
                f"{validation.scenarios_passed}/{validation.scenarios_total} scenarios passed. "
                f"Error: {validation.error_message[:100]}. Retrying..."
            )
            continue

        print(
            f"    [{validation.status}] {problem.problem_id}: "
            f"{validation.scenarios_passed}/{validation.scenarios_total} scenarios passed "
            f"after {retry + 1} attempts. "
            f"Error: {validation.error_message[:100]}"
        )

        return RunRecord(
            problem_id=problem.problem_id,
            source=problem.source,
            function_name=problem.function_name,
            status=validation.status,
            scenarios_passed=validation.scenarios_passed,
            scenarios_total=validation.scenarios_total,
            steps_passed=validation.steps_passed,
            steps_total=validation.steps_total,
            scenario_pass_rate=validation.pass_rate,
            step_pass_rate=validation.step_pass_rate,
            generation_time_s=generation_time_total,
            error_message=validation.error_message[:200],
            retry_count=retry,
        )

    raise RuntimeError("run_single exhausted retry loop without returning")