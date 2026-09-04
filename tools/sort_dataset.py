import json
import re
from pathlib import Path


INPUT_FILE = Path("enhanced_dataset/bdd_dataset.jsonl")
OUTPUT_FILE = Path("enhanced_dataset/bdd_dataset_sorted.jsonl")


def sort_key(record):
    """
    Examples:
        HumanEval_1   -> ("HumanEval", 1)
        HumanEval_150 -> ("HumanEval", 150)
        MBPP_1        -> ("MBPP", 1)
    """
    task_id = record.get("id", "")

    match = re.match(r"^(.*?)_(\d+)$", task_id)
    if match:
        prefix, number = match.groups()
        return prefix, int(number)

    # Fallback for unexpected IDs
    return task_id, float("inf")


def main():
    records = []

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    records.sort(key=sort_key)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Sorted {len(records)} records.")
    print(f"Output written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()