"""
run_pipeline.py — Entry point for the BDD dataset generator.

Usage:
    python run_pipeline.py
    python run_pipeline.py --dry-run
    python run_pipeline.py --humaneval-limit 163
    python run_pipeline.py --mbpp-limit 0
    python run_pipeline.py --new-dataset-limit 20
    python run_pipeline.py --resume
    python run_pipeline.py --list-models
    python run_pipeline.py --check-data
    python run_pipeline.py --diagnose-mbpp
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from config import HUMANEVAL_LIMIT, MBPP_LIMIT


def cmd_list_models() -> None:
    """
    List models available on the Ollama server.
    """
    from llm_client import OllamaClient, OllamaError

    client = OllamaClient()

    try:
        models = client.list_models()
    except OllamaError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("Models available on the Ollama server:")

    for model in models:
        print(f"  {model}")

    print(f"\nCurrent OLLAMA_MODEL in config.py: '{client.model}'")


def cmd_check_data() -> None:
    """
    Verify that HumanEval and MBPP dataset files are readable.
    """
    from data_loader import load_humaneval, load_mbpp

    print("Checking HumanEval...")

    try:
        problems = load_humaneval(limit=3)

        for problem in problems:
            print(f"  OK: {problem.problem_id}  fn={problem.function_name}")

    except FileNotFoundError as e:
        print(f"  ERROR: {e}")

    print("Checking MBPP...")

    try:
        problems = load_mbpp(limit=3)

        for problem in problems:
            print(f"  OK: {problem.problem_id}  fn={problem.function_name}")

    except FileNotFoundError as e:
        print(f"  ERROR: {e}")


def cmd_diagnose_mbpp() -> None:
    """
    Explain why MBPP rows are accepted or skipped.
    """
    from data_loader import diagnose_mbpp

    diagnose_mbpp()


def build_parser() -> argparse.ArgumentParser:
    """
    Build the command-line argument parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "BDD Dataset Generator — generates Gherkin + Behave step files "
            "for HumanEval and MBPP problems using an LLM via Ollama."
        )
    )

    parser.add_argument(
        "--humaneval-limit",
        type=int,
        default=HUMANEVAL_LIMIT,
        help=f"Max HumanEval problems to process (default: {HUMANEVAL_LIMIT})",
    )

    parser.add_argument(
        "--mbpp-limit",
        type=int,
        default=MBPP_LIMIT,
        help=f"Max MBPP problems to process (default: {MBPP_LIMIT})",
    )

    parser.add_argument(
        "--new-dataset-limit",
        type=int,
        default=0,
        help=(
            "Max problems from new_dataset.jsonl to process "
            "(default: 0 = skip)."
        ),
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip problems that already have generated files in generated/",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data and build prompts but don't call the LLM",
    )

    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List models available on the Ollama server and exit",
    )

    parser.add_argument(
        "--check-data",
        action="store_true",
        help="Verify dataset files are present and parseable, then exit",
    )

    parser.add_argument(
        "--diagnose-mbpp",
        action="store_true",
        help=(
            "Print a full breakdown of every row in mbpp.jsonl and why each "
            "is accepted or skipped, then exit."
        ),
    )

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """
    CLI entry point.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_models:
        cmd_list_models()
        return

    if args.check_data:
        cmd_check_data()
        return

    if args.diagnose_mbpp:
        cmd_diagnose_mbpp()
        return

    from generator import run_pipeline

    run_pipeline(
        humaneval_limit=args.humaneval_limit,
        mbpp_limit=args.mbpp_limit,
        new_dataset_limit=args.new_dataset_limit,
        resume=args.resume,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()