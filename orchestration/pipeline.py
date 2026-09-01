"""
Full dataset generation pipeline.
"""

from config import (
    GENERATED_DIR,
    HUMANEVAL_LIMIT,
    MBPP_LIMIT,
    VALIDATED_DATASET_DIR,
)

from data_loader import load_all
from llm_client import OllamaClient
from prompt_builder import build_prompt
from reporter import Reporter

from orchestration.runner import run_single
from orchestration.skip_checks import (
    already_generated,
    in_validated_dataset,
)


def run_pipeline(
    humaneval_limit: int = HUMANEVAL_LIMIT,
    mbpp_limit: int = MBPP_LIMIT,
    new_dataset_limit: int = 0,
    resume: bool = False,
    dry_run: bool = False,
) -> None:
    """
    Run the full generation pipeline.

    Skip logic, in priority order:
        1. Problem exists in validated_dataset/ -> always skip
        2. Problem exists in generated/ -> skip only when --resume is passed
    """
    print("\n" + "=" * 60)
    print("BDD Dataset Generator")
    print("=" * 60)

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    problems = load_all(humaneval_limit, mbpp_limit, new_dataset_limit)
    reporter = Reporter()

    if dry_run:
        print(f"\n[DRY RUN] Would process {len(problems)} problems.")

        if problems:
            print("Prompt sample for first problem:")
            print("-" * 40)
            print(build_prompt(problems[0])[:1000])
            print("-" * 40)
        else:
            print("No problems loaded.")

        return

    client = OllamaClient()

    print("\nChecking Ollama server...")

    if not client.ping():
        print(
            "WARNING: Could not reach Ollama server.\n"
            f"  URL: {client._generate_url}\n"
            "  Make sure you are on the university network or VPN.\n"
            "  Continuing anyway — will fail on first LLM call.\n"
        )
    else:
        print(f"  Server OK. Model: {client.model}")

    if VALIDATED_DATASET_DIR.exists():
        already_validated_count = sum(
            1 for problem in problems if in_validated_dataset(problem)
        )

        if already_validated_count:
            print(
                f"\n  {already_validated_count} problem(s) already in "
                "validated_dataset/ — will be skipped automatically."
            )

    total_problems = len(problems)
    processed_count = 0
    skipped_validated_count = 0
    skipped_resume_count = 0

    print(f"\nProcessing {total_problems} problems...\n")

    for problem in problems:
        processed_count += 1

        if in_validated_dataset(problem):
            print(
                f"  [SKIP-VALIDATED] {problem.problem_id} "
                "— already in validated_dataset/"
            )
            skipped_validated_count += 1
            continue

        if resume and already_generated(problem):
            print(
                f"  [SKIP-RESUME]    {problem.problem_id} "
                "— already in generated/"
            )
            skipped_resume_count += 1
            continue

        print(
            f"\n  [{processed_count}/{total_problems}] "
            f"{problem.problem_id} — {problem.function_name}()"
        )

        record = run_single(problem, client, reporter)
        reporter.record(record)

        if processed_count % 10 == 0:
            reporter.print_progress(processed_count, total_problems)

    reporter.close()

    print(
        "\n[Done]\n"
        f"  Skipped (validated): {skipped_validated_count}\n"
        f"  Skipped (resume):    {skipped_resume_count}"
    )