"""
generator.py — Main orchestration: load → prompt → generate → parse → validate → record.

Skip logic (checked in this order for every problem):
  1. Already in validated_dataset/  → skip unconditionally (clean, verified data)
  2. Already in generated/          → skip only when --resume flag is set
"""

import time
from pathlib import Path

from config import (
    GENERATED_DIR, VALIDATED_DATASET_DIR, LOGS_DIR, LOG_RAW_RESPONSES,
    MAX_RETRIES, HUMANEVAL_LIMIT, MBPP_LIMIT,
)
from data_loader import ProblemRecord, load_all
from llm_client import OllamaClient, OllamaError
from output_parser import parse_and_write, ParseError, count_scenarios, _problem_dir
from prompt_builder import build_prompt
from reporter import Reporter, RunRecord
from validator import validate, ValidationResult


# ── Helpers ──────────────────────────────────────────────────────────────────

def _log_raw(problem: ProblemRecord, attempt: int, raw: str):
    """Save raw LLM response to logs/ for debugging."""
    if not LOG_RAW_RESPONSES:
        return
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = problem.problem_id.replace("/", "_")
    path    = LOGS_DIR / f"{safe_id}_attempt{attempt}.txt"
    path.write_text(raw, encoding="utf-8")


def _safe_id(problem: ProblemRecord) -> str:
    """Convert 'HumanEval/0' → 'HumanEval_0' for use as a directory name."""
    return problem.problem_id.replace("/", "_")


def _has_feature_and_steps(directory: Path) -> bool:
    """
    Return True if the given problem directory contains both a .feature file
    and a _steps.py file. Works for both generated/ and validated_dataset/.
    """
    features_dir = directory / "features"
    steps_dir    = features_dir / "steps"
    if not features_dir.exists():
        return False
    has_feature = any(features_dir.glob("*.feature"))
    has_steps   = steps_dir.exists() and any(steps_dir.glob("*_steps.py"))
    return has_feature and has_steps


def _in_validated_dataset(problem: ProblemRecord) -> bool:
    """
    Check whether this problem already exists in validated_dataset/.
    This check runs on EVERY call to run_pipeline, regardless of --resume.
    """
    problem_dir = VALIDATED_DATASET_DIR / _safe_id(problem)
    return problem_dir.exists() and _has_feature_and_steps(problem_dir)


def _already_generated(problem: ProblemRecord) -> bool:
    """
    Check whether this problem already exists in generated/.
    Only consulted when --resume is passed.
    """
    problem_dir = _problem_dir(problem)
    return problem_dir.exists() and _has_feature_and_steps(problem_dir)


# ── Single problem pipeline ──────────────────────────────────────────────────

def run_single(
    problem: ProblemRecord,
    client:  OllamaClient,
    reporter: Reporter,
) -> RunRecord:
    """
    Process one problem end-to-end. Handles retries internally.
    Returns a RunRecord with the final outcome.
    """
    gen_time_total = 0.0

    # Temperature schedule: low on first attempt for determinism,
    # escalate on retries to break the model out of memorised completions.
    # At temperature 0.2 a hallucinating model produces identical output
    # every retry — escalation is the only way to get a different result.
    _retry_temperatures = [0.2, 0.7, 0.9]

    for retry in range(MAX_RETRIES + 1):
        if retry > 0:
            print(f"    Retry {retry}/{MAX_RETRIES} for {problem.problem_id}...")

        # ── Step 1: Build prompt ─────────────────────────────────────────────
        prompt = build_prompt(problem)

        # ── Step 2: Call LLM (with escalating temperature on retries) ───────
        retry_temp = _retry_temperatures[min(retry, len(_retry_temperatures) - 1)]
        if retry > 0:
            # Temporarily override temperature for this call only
            original_options = dict(client.options)
            client.options["temperature"] = retry_temp
        try:
            raw, gen_time = client.generate(prompt)
            gen_time_total += gen_time
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
                generation_time_s=gen_time_total,
                error_message=str(e)[:200],
                retry_count=retry,
            )
        finally:
            # Restore original temperature after every call (retry or not)
            if retry > 0:
                client.options = original_options

        _log_raw(problem, retry, raw)

        # ── Step 3: Parse ────────────────────────────────────────────────────
        try:
            parsed = parse_and_write(problem, raw)
        except ParseError as e:
            if retry < MAX_RETRIES:
                print(f"    [PARSE FAIL] {problem.problem_id}: {e} — retrying...")
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
                generation_time_s=gen_time_total,
                error_message=str(e)[:200],
                retry_count=retry,
            )

        n_scenarios = count_scenarios(parsed.feature_content)

        # ── Step 4: Validate ─────────────────────────────────────────────────
        vr: ValidationResult = validate(parsed)

        if vr.status == "PASS":
            print(
                f"    [PASS] {problem.problem_id}  "
                f"{vr.scenarios_passed}/{n_scenarios} scenarios  "
                f"({gen_time_total:.1f}s)"
            )
            return RunRecord(
                problem_id=problem.problem_id,
                source=problem.source,
                function_name=problem.function_name,
                status="PASS",
                scenarios_passed=vr.scenarios_passed,
                scenarios_total=vr.scenarios_total or n_scenarios,
                steps_passed=vr.steps_passed,
                steps_total=vr.steps_total,
                scenario_pass_rate=vr.pass_rate,
                step_pass_rate=vr.step_pass_rate,
                generation_time_s=gen_time_total,
                error_message="",
                retry_count=retry,
            )

        # Validation failed
        if retry < MAX_RETRIES:
            print(
                f"    [{vr.status}] {problem.problem_id}: "
                f"{vr.scenarios_passed}/{n_scenarios} scenarios passed. "
                f"Error: {vr.error_message[:100]}. Retrying..."
            )
            continue

        # Exhausted retries
        print(
            f"    [{vr.status}] {problem.problem_id}: "
            f"{vr.scenarios_passed}/{n_scenarios} scenarios passed after {retry+1} attempts. "
            f"Error: {vr.error_message[:100]}"
        )
        return RunRecord(
            problem_id=problem.problem_id,
            source=problem.source,
            function_name=problem.function_name,
            status=vr.status,
            scenarios_passed=vr.scenarios_passed,
            scenarios_total=vr.scenarios_total or n_scenarios,
            steps_passed=vr.steps_passed,
            steps_total=vr.steps_total,
            scenario_pass_rate=vr.pass_rate,
            step_pass_rate=vr.step_pass_rate,
            generation_time_s=gen_time_total,
            error_message=vr.error_message[:200],
            retry_count=retry,
        )

    raise RuntimeError("run_single exhausted retry loop without returning")


# ── Full pipeline ────────────────────────────────────────────────────────────

def run_pipeline(
    humaneval_limit: int  = HUMANEVAL_LIMIT,
    mbpp_limit:      int  = MBPP_LIMIT,
    resume:          bool = False,
    dry_run:         bool = False,
):
    """
    Full pipeline run.

    Skip logic (in priority order):
      1. Problem exists in validated_dataset/  → always skip (no flag needed)
      2. Problem exists in generated/          → skip only when --resume is passed
    """
    print("\n" + "=" * 60)
    print("BDD Dataset Generator")
    print("=" * 60)

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    problems = load_all(humaneval_limit, mbpp_limit)
    reporter = Reporter()

    if dry_run:
        print(f"\n[DRY RUN] Would process {len(problems)} problems.")
        print("Prompt sample for first problem:")
        print("-" * 40)
        print(build_prompt(problems[0])[:1000])
        print("-" * 40)
        return

    client = OllamaClient()
    print(f"\nChecking Ollama server...")
    if not client.ping():
        print(
            "WARNING: Could not reach Ollama server.\n"
            f"  URL: {client._generate_url}\n"
            "  Make sure you are on the university network or VPN.\n"
            "  Continuing anyway — will fail on first LLM call.\n"
        )
    else:
        print(f"  Server OK. Model: {client.model}")

    # ── Count what's already validated ──────────────────────────────────────
    if VALIDATED_DATASET_DIR.exists():
        n_validated = sum(
            1 for p in problems if _in_validated_dataset(p)
        )
        if n_validated:
            print(
                f"\n  {n_validated} problem(s) already in validated_dataset/ "
                f"— will be skipped automatically."
            )

    # ── Main loop ────────────────────────────────────────────────────────────
    n_total        = len(problems)
    n_done         = 0
    n_skip_valid   = 0   # skipped because already in validated_dataset/
    n_skip_resume  = 0   # skipped because --resume and already in generated/

    print(f"\nProcessing {n_total} problems...\n")

    for problem in problems:
        n_done += 1

        # ── Priority 1: already validated — skip unconditionally ─────────────
        if _in_validated_dataset(problem):
            print(f"  [SKIP-VALIDATED] {problem.problem_id} — already in validated_dataset/")
            n_skip_valid += 1
            continue

        # ── Priority 2: already generated — skip only with --resume ──────────
        if resume and _already_generated(problem):
            print(f"  [SKIP-RESUME]    {problem.problem_id} — already in generated/")
            n_skip_resume += 1
            continue

        print(f"\n  [{n_done}/{n_total}] {problem.problem_id} — {problem.function_name}()")
        record = run_single(problem, client, reporter)
        reporter.record(record)

        if n_done % 10 == 0:
            reporter.print_progress(n_done, n_total)

    reporter.close()
    print(
        f"\n[Done]"
        f"  Skipped (validated): {n_skip_valid}"
        f"  Skipped (resume):    {n_skip_resume}"
    )