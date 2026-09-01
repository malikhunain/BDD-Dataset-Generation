"""
Summary generation for pipeline results.
"""

from collections import Counter
from pathlib import Path
from typing import List
from reporting.models import RunRecord


def build_summary(
    records: List[RunRecord],
    csv_path: Path,
    total_elapsed: float,
) -> str:
    """
    Build the human-readable summary written to results/summary.txt.
    """
    if not records:
        return ""

    total = len(records)
    by_status = Counter(record.status for record in records)

    passed = by_status.get("PASS", 0)
    acceptance = passed / total * 100 if total else 0

    by_source = {}

    for source in ["HumanEval", "MBPP"]:
        source_records = [
            record
            for record in records
            if record.source == source
        ]

        source_passed = sum(
            1
            for record in source_records
            if record.status == "PASS"
        )

        by_source[source] = (source_passed, len(source_records))

    average_generation_time = (
        sum(record.generation_time_s for record in records) / total
    )

    average_scenario_pass_rate = (
        sum(record.scenario_pass_rate for record in records) / total
    )

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
        lines.append(f"  {status:<20} {count:>4}  ({count / total * 100:.1f}%)")

    lines += [
        "",
        "Breakdown by dataset:",
    ]

    for source, (source_passed, source_total) in by_source.items():
        source_percentage = source_passed / source_total * 100 if source_total else 0
        lines.append(
            f"  {source:<12} PASS: {source_passed}/{source_total}  "
            f"({source_percentage:.1f}%)"
        )

    lines += [
        "",
        f"Average generation time  : {average_generation_time:.1f}s per problem",
        f"Average scenario pass rate: {average_scenario_pass_rate:.3f}",
        f"Total elapsed            : {total_elapsed:.0f}s",
        "",
        f"Results CSV : {csv_path}",
        f"Generated   : {passed} problems in",
        f"              {Path('generated').resolve()}",
        "=" * 60,
    ]

    return "\n".join(lines)