"""
reporter.py — Writes results CSV and a human-readable summary.

The CSV is useful for analysis; the summary is what you show your professor.
"""

import csv
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from config import RESULTS_DIR
from validator import ValidationResult


@dataclass
class RunRecord:
    """One row in the results CSV — combines generation metadata + validation result."""
    problem_id:        str
    source:            str          # HumanEval | MBPP
    function_name:     str
    status:            str          # PASS | FAIL_PARSE | FAIL_BEHAVE | FAIL_SYNTAX | FAIL_TIMEOUT
    scenarios_passed:  int
    scenarios_total:   int
    steps_passed:      int
    steps_total:       int
    scenario_pass_rate: float
    step_pass_rate:    float
    generation_time_s: float
    error_message:     str
    retry_count:       int


class Reporter:
    """Accumulates RunRecords and writes results to disk."""

    def __init__(self):
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        self._records: List[RunRecord] = []
        self._csv_path     = RESULTS_DIR / "results.csv"
        self._summary_path = RESULTS_DIR / "summary.txt"
        self._start_time   = time.time()
        self._csv_writer   = None
        self._csv_file     = None
        self._init_csv()

    def _init_csv(self):
        self._csv_file = open(self._csv_path, "w", newline="", encoding="utf-8")
        self._csv_writer = csv.DictWriter(
            self._csv_file,
            fieldnames=[
                "problem_id", "source", "function_name", "status",
                "scenarios_passed", "scenarios_total", "steps_passed", "steps_total",
                "scenario_pass_rate", "step_pass_rate",
                "generation_time_s", "retry_count", "error_message",
            ],
        )
        self._csv_writer.writeheader()
        self._csv_file.flush()

    def record(self, record: RunRecord):
        """Append a result. Writes to CSV immediately (crash-safe)."""
        self._records.append(record)
        self._csv_writer.writerow({
            "problem_id":         record.problem_id,
            "source":             record.source,
            "function_name":      record.function_name,
            "status":             record.status,
            "scenarios_passed":   record.scenarios_passed,
            "scenarios_total":    record.scenarios_total,
            "steps_passed":       record.steps_passed,
            "steps_total":        record.steps_total,
            "scenario_pass_rate": f"{record.scenario_pass_rate:.3f}",
            "step_pass_rate":     f"{record.step_pass_rate:.3f}",
            "generation_time_s":  f"{record.generation_time_s:.1f}",
            "retry_count":        record.retry_count,
            "error_message":      record.error_message[:200] if record.error_message else "",
        })
        self._csv_file.flush()

    def print_progress(self, n_done: int, n_total: int):
        """Print a one-line progress update."""
        passed  = sum(1 for r in self._records if r.status == "PASS")
        elapsed = time.time() - self._start_time
        pct     = (n_done / n_total * 100) if n_total else 0
        rate    = (elapsed / n_done) if n_done else 0
        eta     = rate * (n_total - n_done)
        print(
            f"  [{n_done}/{n_total} {pct:.0f}%]  "
            f"PASS: {passed}  "
            f"Elapsed: {elapsed:.0f}s  "
            f"ETA: {eta:.0f}s"
        )

    def close(self):
        """Write the summary file and close the CSV."""
        if self._csv_file:
            self._csv_file.close()
        self._write_summary()

    def _write_summary(self):
        records = self._records
        if not records:
            return

        total         = len(records)
        by_status     = Counter(r.status for r in records)
        passed        = by_status.get("PASS", 0)
        acceptance    = passed / total * 100 if total else 0

        by_source     = {}
        for src in ["HumanEval", "MBPP"]:
            src_recs  = [r for r in records if r.source == src]
            src_pass  = sum(1 for r in src_recs if r.status == "PASS")
            by_source[src] = (src_pass, len(src_recs))

        avg_gen_time  = sum(r.generation_time_s for r in records) / total
        avg_sc_rate   = sum(r.scenario_pass_rate for r in records) / total
        total_elapsed = time.time() - self._start_time

        lines = [
            "=" * 60,
            "BDD DATASET GENERATION — RESULTS SUMMARY",
            "=" * 60,
            "",
            f"Total problems processed : {total}",
            f"PASS (all scenarios pass): {passed}  ({acceptance:.1f}%)",
            "",
            "Breakdown by status:",
        ]
        for status, count in sorted(by_status.items()):
            lines.append(f"  {status:<20} {count:>4}  ({count/total*100:.1f}%)")

        lines += [
            "",
            "Breakdown by dataset:",
        ]
        for src, (sp, st) in by_source.items():
            pct = sp / st * 100 if st else 0
            lines.append(f"  {src:<12} PASS: {sp}/{st}  ({pct:.1f}%)")

        lines += [
            "",
            f"Average generation time  : {avg_gen_time:.1f}s per problem",
            f"Average scenario pass rate: {avg_sc_rate:.3f}",
            f"Total elapsed            : {total_elapsed:.0f}s",
            "",
            f"Results CSV : {self._csv_path}",
            f"Generated   : {sum(1 for r in records if r.status == 'PASS')} problems in",
            f"              {Path('generated').resolve()}",
            "=" * 60,
        ]

        summary = "\n".join(lines)
        self._summary_path.write_text(summary, encoding="utf-8")

        # Also print to stdout
        print("\n" + summary)