"""Dashboard metrics and summary calculations."""

from typing import Any, Dict

import pandas as pd


def calculate_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    total = len(df)

    outcome_column = "Outcome" if "Outcome" in df.columns else None
    evidence_column = "Evidence Uploaded" if "Evidence Uploaded" in df.columns else None

    passed = 0
    failed = 0
    blocked = 0
    not_run = 0

    if outcome_column:
        passed = len(df[df[outcome_column] == "Passed"])
        failed = len(df[df[outcome_column] == "Failed"])
        blocked = len(df[df[outcome_column] == "Blocked"])
        not_run = len(df[df[outcome_column] == "Not Run"])

    pass_rate = round((passed / total) * 100, 2) if total else 0
    fail_rate = round((failed / total) * 100, 2) if total else 0
    execution_rate = round(((total - not_run) / total) * 100, 2) if total else 0

    evidence_compliance = 0
    if passed and evidence_column:
        evidence_compliance = len(df[df[evidence_column] == "Yes"]) / passed * 100

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "not_run": not_run,
        "pass_rate": pass_rate,
        "fail_rate": fail_rate,
        "execution_rate": execution_rate,
        "evidence_compliance": evidence_compliance,
    }
