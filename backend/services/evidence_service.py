"""Evidence attachment retrieval and validation logic."""

from typing import Any, Dict, List, Optional, Tuple

from backend.models.responses import evidence_response
from backend.services.ado_service import fetch_iteration_attachments, fetch_result_attachments
from backend.utils.helpers import attachment_name, attachment_size, extract_run_result_ids


def add_attachments(target: Dict[Tuple[str, str, str, str], str], attachments: List[Dict[str, Any]], source: str) -> None:
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue

        name = attachment_name(attachment)
        key = (
            source,
            str(attachment.get("id") or ""),
            attachment.get("url") or "",
            name,
        )

        if key in target:
            continue

        target[key] = name


def fetch_attachment_details(session: Any, headers: Dict[str, str], org: str, project: str, point: Dict[str, Any]) -> Dict[str, Any]:
    """Returns evidence metadata for a test point."""

    outcome = str(point.get("outcome", "Not Run")).strip()

    if outcome.casefold() != "passed":
        return evidence_response("N/A")

    run_id, result_id = extract_run_result_ids(point)

    if not run_id or not result_id:
        return evidence_response(
            "No Run/Result",
            error="Passed test point is missing lastTestRun or lastResult.",
        )

    found_attachments: Dict[Tuple[str, str, str, str], str] = {}
    errors = []

    result_attachments, error = fetch_result_attachments(session, headers, org, project, run_id, result_id)
    if error:
        errors.append(error)
    add_attachments(found_attachments, result_attachments, "result")

    iteration_attachments, error = fetch_iteration_attachments(session, headers, org, project, run_id, result_id)
    if error:
        errors.append(error)
    add_attachments(found_attachments, iteration_attachments, "iteration")

    count = len(found_attachments)
    files = ", ".join(name for name in found_attachments.values() if name)
    size = 0
    if iteration_attachments:
        size = attachment_size(iteration_attachments[0])

    if errors and count == 0:
        return evidence_response("Error", error="; ".join(errors))

    return evidence_response(
        "Yes" if count > 0 else "No",
        count=count,
        files=files,
        size=size,
        error="; ".join(errors),
    )