import csv

from bdd_pipeline.reporting import Reporter, RunRecord


def _make_record() -> RunRecord:
    return RunRecord(
        problem_id="HumanEval/0",
        source="HumanEval",
        function_name="has_close_elements",
        status="PASS",
        scenarios_passed=5,
        scenarios_total=5,
        steps_passed=15,
        steps_total=15,
        scenario_pass_rate=1.0,
        step_pass_rate=1.0,
        generation_time_s=12.34,
        error_message="",
        retry_count=0,
    )


def test_reporter_writes_csv_row(tmp_path):
    reporter = Reporter(results_dir=tmp_path)

    reporter.record(_make_record())
    reporter.close()

    csv_path = tmp_path / "results.csv"
    assert csv_path.exists()

    with open(csv_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1

    row = rows[0]

    assert row["problem_id"] == "HumanEval/0"
    assert row["source"] == "HumanEval"
    assert row["function_name"] == "has_close_elements"
    assert row["status"] == "PASS"
    assert row["scenarios_passed"] == "5"
    assert row["scenarios_total"] == "5"
    assert row["scenario_pass_rate"] == "1.000"
    assert row["step_pass_rate"] == "1.000"
    assert row["generation_time_s"] == "12.3"
    assert row["retry_count"] == "0"
    assert row["error_message"] == ""


def test_reporter_writes_summary(tmp_path):
    reporter = Reporter(results_dir=tmp_path)

    reporter.record(_make_record())
    reporter.close()

    summary_path = tmp_path / "summary.txt"
    assert summary_path.exists()

    summary = summary_path.read_text(encoding="utf-8")

    assert "BDD DATASET GENERATION — RESULTS SUMMARY" in summary
    assert "Total problems processed : 1" in summary
    assert "PASS (all scenarios pass): 1" in summary
    assert "HumanEval" in summary


def test_empty_reporter_does_not_write_summary(tmp_path):
    reporter = Reporter(results_dir=tmp_path)
    reporter.close()

    assert (tmp_path / "results.csv").exists()
    assert not (tmp_path / "summary.txt").exists()
