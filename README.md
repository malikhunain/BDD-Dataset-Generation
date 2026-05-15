# BDD Dataset Generator

A pipeline for generating **Behavior-Driven Development (BDD)** test specifications for Python coding problems. Given problems from the [HumanEval](https://github.com/openai/human-eval) and [MBPP](https://huggingface.co/datasets/google-research-datasets/mbpp) benchmarks, it uses an LLM (via [Ollama](https://ollama.com)) to generate Gherkin feature files and Python [Behave](https://behave.readthedocs.io/) step definitions, then validates them by executing Behave against the reference solution.

This pipeline is part of a research project investigating whether BDD-derived reward signals improve LLM code synthesis quality when used for Reinforcement Learning (RL) fine-tuning.

---

## How It Works

```
HumanEval / MBPP problems
        ↓
  LLM (via Ollama)
        ↓
  Gherkin .feature file
  Behave _steps.py file
        ↓
  Behave executes against reference solution
        ↓
  PASS → moved to validated_dataset/
  FAIL → stays in generated/ for retry
```

Each entry in `validated_dataset/` is a complete, executable BDD test suite for one coding problem — ready to be used as a reward signal in RL training.

---

## Project Structure

```
bdd-dataset-generator/
│
├── config.py             # All settings: Ollama URL, model, paths, limits
├── data_loader.py        # Loads HumanEval + MBPP from local JSONL files
├── llm_client.py         # Ollama API client (supports thinking models)
├── prompt_builder.py     # Builds the generation prompt with few-shot examples
├── output_parser.py      # Parses LLM output into .feature + _steps.py files
├── validator.py          # Runs Behave against reference solution
├── generator.py          # Main orchestration loop
├── reporter.py           # Writes results CSV + summary statistics
├── revalidate.py         # Re-runs Behave, moves passing problems to validated_dataset/
├── run.py                # Entry point
│
├── dataset/              # PUT YOUR DATA FILES HERE (git-ignored)
│   ├── HumanEval.jsonl
│   └── mbpp.jsonl
│
├── generated/            # Intermediate output (git-ignored)
│   └── HumanEval_0/
│       ├── solution.py
│       └── features/
│           ├── has_close_elements.feature
│           └── steps/
│               └── has_close_elements_steps.py
│
├── validated_dataset/    # Final verified output (git-ignored)
│   └── HumanEval_0/      # Only problems where all Behave scenarios passed
│
├── results/              # CSV reports and summaries (git-ignored)
│   ├── results.csv
│   ├── revalidate_results.csv
│   └── summary.txt
│
└── logs/                 # Raw LLM responses for debugging (git-ignored)
    └── HumanEval_0_attempt0.txt
```

---

## Requirements

- Python 3.10+
- Access to an [Ollama](https://ollama.com) server with a capable model
- Tested with: `gpt-oss:120b`, `qwen3.30:30b`
- For **thinking models** (Qwen3, DeepSeek-R1, etc.): set `IS_THINKING_MODEL = True` and `num_predict >= 16384` in `config.py`

```bash
pip install requests behave datasets
```

---

## Setup

### 1. Configure the Ollama server

Open `config.py` and update:

```python
OLLAMA_BASE_URL   = "https://your-ollama-server/ollama"
OLLAMA_MODEL      = "gpt-oss:120b"    # exact name shown by --list-models
IS_THINKING_MODEL = False             # set True for Qwen3, DeepSeek-R1, etc.
```

Check which models are available on your server:

```bash
python run.py --list-models
```

### 2. Download the dataset files

**HumanEval**

```bash
python3 -c "
from datasets import load_dataset; import json
ds = load_dataset('openai/openai_humaneval', split='test')
with open('dataset/HumanEval.jsonl', 'w') as f:
    [f.write(json.dumps(r) + '\n') for r in ds]
print(f'Saved {len(ds)} problems')
"
```

**MBPP**

```bash
python3 -c "
from datasets import load_dataset; import json
ds = load_dataset('google-research-datasets/mbpp', split='train')
with open('dataset/mbpp.jsonl', 'w') as f:
    [f.write(json.dumps(r) + '\n') for r in ds]
print(f'Saved {len(ds)} problems')
"
```

Verify both files are readable:

```bash
python run.py --check-data
```

---

## Usage

### Step 1 — Generate

```bash
# Full run: 100 problems from each dataset
python run.py

# Pilot: 5 problems only (test your setup first)
python run.py --humaneval-limit 5 --mbpp-limit 5

# Preview the prompt without calling the LLM
python run.py --dry-run

# Resume an interrupted run (skips problems already in generated/)
python run.py --resume
```

> Problems already present in `validated_dataset/` are **always skipped automatically** — no flag needed.

### Step 2 — Validate and promote

Run Behave on everything in `generated/`. Passing problems are automatically moved to `validated_dataset/`:

```bash
# Validate all → move passing ones
python revalidate.py

# Validate but do not move anything (inspection only)
python revalidate.py --no-move

# Only one dataset
python revalidate.py --source HumanEval
python revalidate.py --source MBPP

# Specific problems only
python revalidate.py --ids HumanEval_2 MBPP_603

# Re-validate only the ones that failed last time
python revalidate.py --failed-only

# Print full Behave output for every failure
python revalidate.py --verbose
```

### Full workflow

```bash
# 1. Generate
python run.py --humaneval-limit 100 --mbpp-limit 100

# 2. Validate and promote passing ones automatically
python revalidate.py

# 3. Inspect failures, optionally fix step files manually
#    (edit files inside generated/HumanEval_X/features/steps/)

# 4. Re-test the ones you fixed
python revalidate.py --failed-only

# 5. Generate replacements for anything still failing
#    (validated_dataset/ entries are skipped automatically)
python run.py --humaneval-limit 100 --mbpp-limit 100
```

---

## Output Format

### results/results.csv

Written incrementally — safe if the run is interrupted.

| Column               | Description                                                        |
| -------------------- | ------------------------------------------------------------------ |
| `problem_id`         | e.g. `HumanEval/0`, `MBPP/602`                                     |
| `source`             | `HumanEval` or `MBPP`                                              |
| `function_name`      | e.g. `has_close_elements`                                          |
| `status`             | `PASS` / `FAIL_PARSE` / `FAIL_BEHAVE` / `FAIL_SYNTAX` / `FAIL_LLM` |
| `scenarios_passed`   | Behave scenarios that passed                                       |
| `scenarios_total`    | Total Behave scenarios generated                                   |
| `scenario_pass_rate` | `scenarios_passed / scenarios_total`                               |
| `step_pass_rate`     | Step-level pass rate                                               |
| `generation_time_s`  | Seconds the LLM took                                               |
| `retry_count`        | LLM retries needed                                                 |
| `error_message`      | Error detail (if status != PASS)                                   |

### results/revalidate_results.csv

Same columns as above, plus `moved_to_validated` (`True`/`False`).

### validated_dataset/ structure

```
validated_dataset/
└── HumanEval_0/
    ├── solution.py                          # reference solution (ground truth)
    └── features/
        ├── has_close_elements.feature       # Gherkin specification
        └── steps/
            └── has_close_elements_steps.py  # Behave step definitions
```

---

## Failure Status Reference

| Status         | Meaning                                        | What to do                                                  |
| -------------- | ---------------------------------------------- | ----------------------------------------------------------- |
| `PASS`         | All scenarios passed                           | Moved to `validated_dataset/` automatically                 |
| `FAIL_PARSE`   | LLM output could not be parsed                 | Auto-retried; check `logs/` for raw response                |
| `FAIL_SYNTAX`  | Step file has Python errors or undefined steps | Edit step file manually, then `revalidate.py --failed-only` |
| `FAIL_BEHAVE`  | Parsed OK but scenarios failed                 | Wrong expected values; auto-retried                         |
| `FAIL_LLM`     | Ollama API error or empty response             | Check server; increase `num_predict` for thinking models    |
| `FAIL_TIMEOUT` | Behave timed out                               | Increase `BEHAVE_TIMEOUT` in `config.py`                    |

---

## Configuration Reference

All settings are in `config.py`.

| Setting             | Default | Description                                     |
| ------------------- | ------- | ----------------------------------------------- |
| `OLLAMA_BASE_URL`   | —       | Ollama server URL                               |
| `OLLAMA_MODEL`      | —       | Model name (use `--list-models` to find it)     |
| `IS_THINKING_MODEL` | `False` | `True` for Qwen3, DeepSeek-R1 and similar       |
| `OLLAMA_TIMEOUT`    | `300`   | Seconds per LLM request                         |
| `num_predict`       | `16384` | Max output tokens; thinking models need ≥ 16384 |
| `HUMANEVAL_LIMIT`   | `100`   | Max HumanEval problems per run                  |
| `MBPP_LIMIT`        | `100`   | Max MBPP problems per run                       |
| `TARGET_SCENARIOS`  | `5`     | Gherkin scenarios to generate per problem       |
| `MAX_RETRIES`       | `2`     | Retry attempts on failure                       |
| `BEHAVE_TIMEOUT`    | `30`    | Seconds per Behave execution                    |
| `LOG_RAW_RESPONSES` | `True`  | Save raw LLM output to `logs/`                  |

---

## Research Context

This pipeline is part of a 6-month research project (April–September 2025) investigating:

> **Can BDD-derived reward signals improve LLM code synthesis quality when used for Reinforcement Learning fine-tuning, compared to standard unit-test reward signals?**

The `validated_dataset/` produced by this pipeline is the training corpus for an RL fine-tuning pipeline built on [HuggingFace TRL](https://github.com/huggingface/trl) with [Qwen2.5-Coder-7B](https://huggingface.co/Qwen/Qwen2.5-Coder-7B) as the base model. Each Gherkin scenario serves as an executable reward signal: the model generates code, Behave runs the scenarios, and the scenario pass rate becomes the reward.

Related benchmarks used for evaluation: HumanEval+, MBPP+.

---

## License

MIT
