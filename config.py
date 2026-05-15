"""
config.py — All configuration for the BDD dataset generator.
Change values here; don't hardcode them elsewhere.
"""

from pathlib import Path

ROOT_DIR = Path(__file__).parent

# ── Ollama API ──────────────────────────────────────────────────────────────
OLLAMA_BASE_URL   = "https://genai-01.uni-hildesheim.de/ollama"
OLLAMA_MODEL      = "gpt-oss:120b"  #"gemma4:31b"
IS_THINKING_MODEL = True
OLLAMA_TIMEOUT    = 300
OLLAMA_OPTIONS    = {
    "temperature": 0.2,
    "num_predict": 16384,
    "top_p": 0.9,
}

# ── Dataset files ───────────────────────────────────────────────────────────
HUMANEVAL_JSONL = ROOT_DIR / "dataset" / "HumanEval.jsonl"
MBPP_JSONL      = ROOT_DIR / "dataset" / "mbpp.jsonl"

# ── Output directories ──────────────────────────────────────────────────────
GENERATED_DIR   = ROOT_DIR / "generated"
RESULTS_DIR     = ROOT_DIR / "results"
LOGS_DIR        = ROOT_DIR / "logs"

# Problems you have manually verified and moved here after revalidate.py.
# The generator checks this directory automatically on every run —
# any problem already present here is skipped without calling the LLM.
# Structure mirrors generated/:  validated_dataset/HumanEval_0/  etc.
VALIDATED_DATASET_DIR = ROOT_DIR / "validated_dataset"

# ── Generation limits ───────────────────────────────────────────────────────
HUMANEVAL_LIMIT  = 100
MBPP_LIMIT       = 100
TARGET_SCENARIOS = 5

# ── Validation ──────────────────────────────────────────────────────────────
BEHAVE_TIMEOUT = 30

# ── Retry logic ─────────────────────────────────────────────────────────────
MAX_RETRIES = 2

# ── Logging ─────────────────────────────────────────────────────────────────
LOG_RAW_RESPONSES = True