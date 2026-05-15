"""
run.py — Entry point for the BDD dataset generator.

Usage:
    python run.py                          # full run: 100 HumanEval + 100 MBPP
    python run.py --dry-run                # inspect prompt, no LLM calls
    python run.py --humaneval-limit 10     # only 10 HumanEval problems
    python run.py --mbpp-limit 0           # skip MBPP entirely
    python run.py --resume                 # skip already-generated problems
    python run.py --list-models            # list models available on Ollama server
    python run.py --check-data             # verify dataset files exist and are readable
"""

import argparse
import sys

from config import HUMANEVAL_LIMIT, MBPP_LIMIT


def cmd_list_models():
    from llm_client import OllamaClient, OllamaError
    client = OllamaClient()
    try:
        models = client.list_models()
        print("Models available on the Ollama server:")
        for m in models:
            print(f"  {m}")
        print(f"\nCurrent OLLAMA_MODEL in config.py: '{client.model}'")
    except OllamaError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_check_data():
    """Verify that dataset files are present and parse correctly."""
    from data_loader import load_humaneval, load_mbpp
    print("Checking HumanEval...")
    try:
        he = load_humaneval(limit=3)
        for p in he:
            print(f"  OK: {p.problem_id}  fn={p.function_name}")
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")

    print("Checking MBPP...")
    try:
        mb = load_mbpp(limit=3)
        for p in mb:
            print(f"  OK: {p.problem_id}  fn={p.function_name}")
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="BDD Dataset Generator — generates Gherkin + Behave step files "
                    "for HumanEval and MBPP problems using Llama via Ollama."
    )
    parser.add_argument(
        "--humaneval-limit", type=int, default=HUMANEVAL_LIMIT,
        help=f"Max HumanEval problems to process (default: {HUMANEVAL_LIMIT})",
    )
    parser.add_argument(
        "--mbpp-limit", type=int, default=MBPP_LIMIT,
        help=f"Max MBPP problems to process (default: {MBPP_LIMIT})",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip problems that already have generated files",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Load data and build prompts but don't call the LLM",
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="List models available on the Ollama server and exit",
    )
    parser.add_argument(
        "--check-data", action="store_true",
        help="Verify dataset files are present and parseable, then exit",
    )

    args = parser.parse_args()

    if args.list_models:
        cmd_list_models()
        return

    if args.check_data:
        cmd_check_data()
        return

    from generator import run_pipeline
    run_pipeline(
        humaneval_limit=args.humaneval_limit,
        mbpp_limit=args.mbpp_limit,
        resume=args.resume,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()