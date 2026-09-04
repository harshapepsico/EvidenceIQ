"""Generic helpers shared by services and processing modules."""

import re
from typing import Any, Dict


def response_error_message(exc: Exception) -> str:
    error = str(exc)
    response = getattr(exc, "response", None)

    if response is not None:
        body = response.text.replace("\n", " ").strip()[:300]
        error = f"{response.status_code} {response.reason}"
        if body:
            error = f"{error}: {body}"

    return error


def attachment_name(attachment: Dict[str, Any]) -> str:
    if not isinstance(attachment, dict):
        return ""
    return attachment.get("fileName") or attachment.get("name") or ""


def attachment_size(attachment: Dict[str, Any]) -> int:
    return attachment.get("size") or 0


def extract_run_result_ids(point: Dict[str, Any]) -> tuple[str | None, str | None]:
    run = point.get("lastTestRun")
    result = point.get("lastResult")

    run = run if isinstance(run, dict) else {}
    result = result if isinstance(result, dict) else {}

    run_id = str(run.get("id") or "").strip() or None
    result_id = str(result.get("id") or "").strip() or None

    if run_id and result_id:
        return run_id, result_id

    result_url = result.get("url")
    if result_url:
        match = re.search(r"/Runs/([^/]+)/Results/([^/?#]+)", result_url, flags=re.IGNORECASE)
        if match:
            run_id = run_id or match.group(1)
            result_id = result_id or match.group(2)

    return run_id, result_id
