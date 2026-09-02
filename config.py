"""
config.py — All configuration for the BDD dataset generator.

Change values here; do not hardcode them elsewhere.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Ollama API
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = "gpt-oss:120b"
IS_THINKING_MODEL = True
OLLAMA_TIMEOUT = 400

OLLAMA_OPTIONS = {
    "temperature": 0.2,
    "num_predict": 16384,
    "top_p": 0.9,
    "num_ctx": 32768,
}


# ---------------------------------------------------------------------------
# Dataset files
# ---------------------------------------------------------------------------
HUMANEVAL_JSONL = ROOT_DIR / "dataset" / "HumanEval.jsonl"
MBPP_JSONL = ROOT_DIR / "dataset" / "mbpp.jsonl"

# New unified-format dataset containing HumanEval_NEW_* and MBPP_NEW_* records.
#
# Expected schema for validated entries:
#   id
#   source
#   source_id
#   description
#   entry_point
#   solution_code
#   test_code
#   tests_passed
#   validation
NEW_DATASET_JSONL = ROOT_DIR / "dataset" / "new_dataset.jsonl"
NEW_DATASET_LIMIT = 500  # Set to 0 to skip this dataset.


# ---------------------------------------------------------------------------
# Output directories
# ---------------------------------------------------------------------------
GENERATED_DIR = ROOT_DIR / "generated"
RESULTS_DIR = ROOT_DIR / "results"
LOGS_DIR = ROOT_DIR / "logs"

# Problems that have been manually verified and moved here after revalidate.py.
#
# The generator checks this directory automatically on every run.
# Any problem already present here is skipped without calling the LLM.
#
# Structure mirrors generated/:
#   validated_dataset/HumanEval_0/
#   validated_dataset/MBPP_100/
VALIDATED_DATASET_DIR = ROOT_DIR / "validated_dataset"


# ---------------------------------------------------------------------------
# Generation limits
# ---------------------------------------------------------------------------
HUMANEVAL_LIMIT = 164
MBPP_LIMIT = 974
TARGET_SCENARIOS = 5


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
BEHAVE_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------
MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_RAW_RESPONSES = True

# ---------------------------------------------------------------------------
# Dataset export
# ---------------------------------------------------------------------------
EXPORT_DIR = ROOT_DIR / "enhanced_dataset"
EXPORT_DATASET_JSONL = EXPORT_DIR / "bdd_dataset.jsonl"