"""Helpers for transforming raw Azure DevOps data into dashboard-friendly records."""

from typing import Any, Dict, List

import pandas as pd


def normalize_suite_ids(suite_ids: Any) -> List[int]:
    if isinstance(suite_ids, int):
        return [suite_ids]

    if isinstance(suite_ids, str):
        return [int(x.strip()) for x in suite_ids.split(",") if x.strip()]

    return list(suite_ids)


def build_record(suite_id: int, point: Dict[str, Any], attachment: Dict[str, Any]) -> Dict[str, Any]:
    test_case = point.get("testCase", {})
    assigned = point.get("assignedTo", {})
    configuration = point.get("configuration", {})

    return {
        "Suite ID": suite_id,
        "Test Point ID": point.get("id", "N/A"),
        "Test Case ID": test_case.get("id", "N/A"),
        "Test Case Name": test_case.get("name", "N/A"),
        "Outcome": point.get("outcome", "Not Run"),
        "State": point.get("state", "N/A"),
        "Current Tester": (
            assigned.get("displayName", "Unassigned")
            if isinstance(assigned, dict)
            else assigned
        ),
        "Configuration": configuration.get("name", "N/A"),
        "Evidence Uploaded": attachment["Evidence Uploaded"],
        "Evidence Count": attachment["Evidence Count"],
        "Evidence Files": attachment["Evidence Files"],
        "Evidence Validation": "Validated" if attachment["Evidence Size"] > 1 else "Not Validated",
    }


def build_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(records)

    if not df.empty:
        df = df.drop_duplicates(subset=["Test Point ID"]).reset_index(drop=True)

    return df
