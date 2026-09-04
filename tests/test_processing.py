import pandas as pd

from backend.processing.metrics import calculate_metrics
from backend.processing.transformers import build_dataframe, build_record


def test_build_record_marks_validated_evidence():
    point = {
        "id": 1,
        "outcome": "Passed",
        "state": "Active",
        "testCase": {"id": 7, "name": "TC-001"},
        "assignedTo": {"displayName": "Alice"},
        "configuration": {"name": "Config A"},
    }
    attachment = {
        "Evidence Uploaded": "Yes",
        "Evidence Count": 1,
        "Evidence Files": "evidence.png",
        "Evidence Size": 250,
    }

    record = build_record(123, point, attachment)

    assert record["Test Case Name"] == "TC-001"
    assert record["Run By"] == "N/A"
    assert record["Evidence Validation"] == "Validated"


def test_build_record_displays_bug_status_by_outcome():
    attachment = {
        "Evidence Uploaded": "N/A",
        "Evidence Count": 0,
        "Evidence Files": "",
        "Evidence Size": 0,
    }

    failed_point = {"outcome": "Failed", "testCase": {"id": 1}}
    passed_point = {"outcome": "Passed", "testCase": {"id": 2}}

    assert build_record(1, failed_point, attachment, bug_attached=True)["Bug Attached"] == "Yes"
    assert build_record(1, failed_point, attachment, bug_attached=False)["Bug Attached"] == "No"
    assert build_record(1, passed_point, attachment, bug_attached=True)["Bug Attached"] == "N/A"


def test_build_record_displays_run_by():
    attachment = {
        "Evidence Uploaded": "N/A",
        "Evidence Count": 0,
        "Evidence Files": "",
        "Evidence Size": 0,
    }
    point = {"outcome": "Failed", "testCase": {"id": 1}}

    record = build_record(1, point, attachment, run_by="Alice")

    assert record["Run By"] == "Alice"
    assert "Current Tester" not in record


def test_build_dataframe_drops_duplicate_test_points():
    records = [
        {"Test Point ID": 1, "Outcome": "Passed"},
        {"Test Point ID": 1, "Outcome": "Passed"},
        {"Test Point ID": 2, "Outcome": "Failed"},
    ]

    df = build_dataframe(records)

    assert len(df) == 2
    assert list(df["Test Point ID"]) == [1, 2]


def test_calculate_metrics_returns_expected_summary():
    df = pd.DataFrame(
        [
            {"Outcome": "Passed", "Evidence Uploaded": "Yes"},
            {"Outcome": "Passed", "Evidence Uploaded": "No"},
            {"Outcome": "Failed", "Evidence Uploaded": "No"},
            {"Outcome": "Unspecified", "Evidence Uploaded": "N/A"},
            {"Outcome": "NotApplicable", "Evidence Uploaded": "N/A"},
            {"Outcome": "Not Run", "Evidence Uploaded": "N/A"},
        ]
    )

    metrics = calculate_metrics(df)

    assert metrics["total"] == 6
    assert metrics["passed"] == 2
    assert metrics["failed"] == 1
    assert metrics["not_run"] == 3
    assert metrics["pass_rate"] == 33.33
    assert metrics["fail_rate"] == 16.67
    assert metrics["execution_rate"] == 50.0
    assert metrics["evidence_compliance"] == 50.0
