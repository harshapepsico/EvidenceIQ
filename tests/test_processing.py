import pandas as pd

from evidenceiq.processing.metrics import calculate_metrics
from evidenceiq.processing.transformers import build_dataframe, build_record


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
    assert record["Current Tester"] == "Alice"
    assert record["Evidence Validation"] == "Validated"


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
            {"Outcome": "Not Run", "Evidence Uploaded": "N/A"},
        ]
    )

    metrics = calculate_metrics(df)

    assert metrics["total"] == 4
    assert metrics["passed"] == 2
    assert metrics["failed"] == 1
    assert metrics["not_run"] == 1
    assert metrics["pass_rate"] == 50.0
    assert metrics["evidence_compliance"] == 50.0
