"""
Utilities for reading previous pipeline results.
"""

import csv
from pathlib import Path
from typing import Set


def load_failed_ids(results_csv: Path) -> Set[str]:
    """
    Read results.csv and return the set of problem_ids that did not PASS.
    """
    if not results_csv.exists():
        print(f"[revalidate] No existing results.csv at {results_csv}")
        return set()

    failed = set()

    with open(results_csv, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            if row.get("status", "") != "PASS":
                failed.add(row["problem_id"])

    return failed