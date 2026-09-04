"""Helpers for transforming raw Azure DevOps data into dashboard-friendly records."""

from typing import Any, Dict, List, Optional

import pandas as pd


def normalize_suite_ids(suite_ids: Any) -> List[int]:
    if isinstance(suite_ids, int):
        return [suite_ids]

    if isinstance(suite_ids, str):
        return [int(x.strip()) for x in suite_ids.split(",") if x.strip()]

    return list(suite_ids)


def build_record(
    suite_id: int,
    point: Dict[str, Any],
    attachment: Dict[str, Any],
    bug_attached: Optional[bool] = None,
    run_by: Optional[str] = None,
) -> Dict[str, Any]:
    test_case = point.get("testCase", {})
    test_case = test_case if isinstance(test_case, dict) else {}
    assigned = point.get("assignedTo", {})
    configuration = point.get("configuration", {})
    configuration = configuration if isinstance(configuration, dict) else {}

    attachment = attachment or {}

    outcome = str(point.get("outcome", "Not Run")).strip()
    bug_status = "N/A"
    if outcome.casefold() == "failed":
        bug_status = "Yes" if bug_attached else "No"

    return {
        "Suite ID": suite_id,
        "Test Point ID": point.get("id", "N/A"),
        "Test Case ID": test_case.get("id", "N/A"),
        "Test Case Name": test_case.get("name", "N/A"),
        "Outcome": point.get("outcome", "Not Run"),
        "Bug Attached": bug_status,
        "State": point.get("state", "N/A"),
        "Run By": run_by or "N/A",
        "Configuration": configuration.get("name", "N/A"),
        "Evidence Uploaded": attachment.get("Evidence Uploaded", "N/A"),
        "Evidence Count": attachment.get("Evidence Count", 0),
        "Evidence Files": attachment.get("Evidence Files", ""),
        "Evidence Validation": "Validated" if attachment.get("Evidence Size", 0) > 1 else "Not Validated",
    }


def build_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(records)

    if not df.empty:
        df = df.drop_duplicates(subset=["Test Point ID"]).reset_index(drop=True)

    return df
