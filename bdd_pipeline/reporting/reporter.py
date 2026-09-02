"""
Reporter implementation.

Accumulates RunRecords, writes results.csv incrementally, and writes a final
summary.txt when closed.
"""

import csv
import time
from pathlib import Path
from typing import List, Optional

from config import RESULTS_DIR

from bdd_pipeline.reporting.csv_rows import CSV_FIELDNAMES, to_csv_row
from bdd_pipeline.reporting.models import RunRecord
from bdd_pipeline.reporting.summary import build_summary


class Reporter:
    """
    Accumulates RunRecords and writes results to disk.

    The CSV file is opened and initialized when the Reporter is created.
    Creating a Reporter immediately creates or overwrites results/results.csv.
    """

    def __init__(self, results_dir: Optional[Path] = None):
        self._results_dir = (
            Path(results_dir)
            if results_dir is not None
            else RESULTS_DIR
        )

        self._results_dir.mkdir(parents=True, exist_ok=True)

        self._records: List[RunRecord] = []
        self._csv_path = self._results_dir / "results.csv"
        self._summary_path = self._results_dir / "summary.txt"
        self._start_time = time.time()

        self._csv_writer = None
        self._csv_file = None

        self._init_csv()

    def _init_csv(self) -> None:
        """
        Open the CSV file and write the header.

        This happens immediately on Reporter construction so that an interrupted
        run still leaves a valid CSV behind.
        """
        self._csv_file = open(
            self._csv_path,
            "w",
            newline="",
            encoding="utf-8",
        )

        self._csv_writer = csv.DictWriter(
            self._csv_file,
            fieldnames=CSV_FIELDNAMES,
        )

        self._csv_writer.writeheader()
        self._csv_file.flush()

    def record(self, record: RunRecord) -> None:
        """
        Append a result.

        Writes to CSV immediately for crash safety.
        """
        self._records.append(record)

        self._csv_writer.writerow(to_csv_row(record))
        self._csv_file.flush()

    def print_progress(self, n_done: int, n_total: int) -> None:
        """
        Print a one-line progress update.
        """
        passed = sum(1 for record in self._records if record.status == "PASS")
        elapsed = time.time() - self._start_time

        percentage = (n_done / n_total * 100) if n_total else 0
        rate = (elapsed / n_done) if n_done else 0
        eta = rate * (n_total - n_done)

        print(
            f"  [{n_done}/{n_total} {percentage:.0f}%]  "
            f"PASS: {passed}  "
            f"Elapsed: {elapsed:.0f}s  "
            f"ETA: {eta:.0f}s"
        )

    def close(self) -> None:
        """
        Close the CSV and write the summary file.
        """
        if self._csv_file:
            self._csv_file.close()

        self._write_summary()

    def _write_summary(self) -> None:
        """
        Write results/summary.txt and print the summary to stdout.
        """
        records = self._records

        if not records:
            return

        total_elapsed = time.time() - self._start_time

        summary = build_summary(
            records=records,
            csv_path=self._csv_path,
            total_elapsed=total_elapsed,
        )

        self._summary_path.write_text(summary, encoding="utf-8")

        print("\n" + summary)