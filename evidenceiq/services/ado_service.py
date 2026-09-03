"""Azure DevOps service layer with recursive suites and tester fallback."""

import os
import random
import time
from typing import Any, Callable, Dict, List, Optional
import xml.etree.ElementTree as ET
import xml

import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

from evidenceiq.config.settings import (
    ADO_BACKOFF_SECONDS,
    ADO_MAX_BACKOFF_SECONDS,
    ADO_MAX_RETRIES,
    API_VERSION,
    MAX_WORKERS,
    ORG,
    POINT_PAGE_SIZE,
    get_pat,
)
from evidenceiq.models.responses import evidence_response
from evidenceiq.processing.transformers import build_dataframe, build_record
from evidenceiq.utils.helpers import extract_run_result_ids, response_error_message


def validate_environment(project: str, plan_id: str, pat: Optional[str] = None) -> None:
    required_values = {
        "Organization": ORG,
        "Project": project,
        "PAT": pat or get_pat(),
        "Test Plan ID": plan_id,
    }
    missing = [name for name, value in required_values.items() if not value]

    if missing:
        raise ValueError(
            "Missing required Azure DevOps environment variables: " + ", ".join(missing)
        )


def _retry_delay(response: Optional[requests.Response], retry_number: int) -> float:
    retry_after = response.headers.get("Retry-After") if response is not None else None
    try:
        return max(0.0, float(retry_after))
    except (TypeError, ValueError):
        delay = ADO_BACKOFF_SECONDS * (2 ** (retry_number - 1))
        return min(ADO_MAX_BACKOFF_SECONDS, delay) + random.uniform(0, 0.25)


def fetch_json(
    session: requests.Session,
    url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]] = None,
    include_response: bool = False,
):
    """Fetch JSON while honoring ADO throttling and transient failures."""
    response = None
    last_error = None

    for attempt in range(ADO_MAX_RETRIES + 1):
        try:
            response = session.get(url, headers=headers, params=params, timeout=30)
            if response.status_code not in {408, 429, *range(500, 600)}:
                if response.status_code >= 400:
                    result = (None, response_error_message(requests.HTTPError(response=response)))
                    return (*result, response) if include_response else result
                data = response.json()
                return (data, "", response) if include_response else (data, "")
            last_error = requests.HTTPError(response=response)
        except requests.RequestException as exc:
            last_error = exc
            response = getattr(exc, "response", None)
        except ValueError as exc:
            result = (None, f"Invalid JSON response: {exc}")
            return (*result, response) if include_response else result

        if attempt >= ADO_MAX_RETRIES:
            break

        retry_number = attempt + 1
        delay = _retry_delay(response, retry_number)
        status = response.status_code if response is not None else "request error"
        print(f"Retrying ADO request after {status}; attempt {retry_number} in {delay:.2f}s")
        time.sleep(delay)

    result = (None, response_error_message(last_error or requests.RequestException("ADO request failed")))
    return (*result, response) if include_response else result


def fetch_result_attachments(session: requests.Session, headers: Dict[str, str], org: str, project: str, run_id: str, result_id: str):
    attachment_url = (
        f"https://dev.azure.com/{org}/{project}"
        f"/_apis/test/Runs/{run_id}/Results/{result_id}/attachments"
    )

    data, error = fetch_json(
        session,
        attachment_url,
        headers,
        params={"api-version": API_VERSION},
    )

    if error:
        return [], f"Result attachments: {error}"

    return data.get("value", []), ""


def fetch_iteration_attachments(session: requests.Session, headers: Dict[str, str], org: str, project: str, run_id: str, result_id: str):
    iterations_url = (
        f"https://dev.azure.com/{org}/{project}"
        f"/_apis/test/Runs/{run_id}/Results/{result_id}/iterations"
    )

    data, error = fetch_json(
        session,
        iterations_url,
        headers,
        params={
            "includeActionResults": "true",
            "api-version": API_VERSION,
        },
    )

    if error:
        return [], f"Iteration attachments: {error}"

    attachments = []

    for iteration in data.get("value", []):
        attachments.extend(iteration.get("attachments") or [])
        for action in iteration.get("actionResults") or []:
            attachments.extend(action.get("attachments") or [])

    return attachments, ""


def create_session(pat: Optional[str] = None) -> requests.Session:
    session = requests.Session()
    session.auth = HTTPBasicAuth("", pat or get_pat())
    return session


def fetch_all_suite_ids(session: requests.Session, headers: Dict[str, str], org: str, project: str, plan_id: str) -> List[int]:
    suites_url = (
        f"https://dev.azure.com/{org}/{project}"
        f"/_apis/testplan/Plans/{plan_id}/Suites"
        f"?api-version=7.1-preview.1"
    )

    suite_ids = []
    continuation_token = None

    while True:
        params = {"api-version": "7.1-preview.1"}
        if continuation_token:
            params["continuationToken"] = continuation_token
        data, error, response = fetch_json(
            session, suites_url, headers, params=params, include_response=True
        )
        if error:
            raise RuntimeError(f"Unable to fetch plan suites: {error}")

        suites = data.get("value", [])
        suite_ids.extend(
            suite["id"]
            for suite in suites
            if isinstance(suite, dict) and "id" in suite
        )
        continuation_token = (
            data.get("continuationToken")
            or data.get("continuationtoken")
            or response.headers.get("x-ms-continuationtoken")
            or response.headers.get("x-ms-continuation-token")
        )
        if not continuation_token:
            break

    return suite_ids


def resolve_suite_ids(suite_ids: Optional[Any], fallback_input: str, session: requests.Session, headers: Dict[str, str], org: str, project: str, plan_id: str) -> List[int]:
    if suite_ids is not None:
        return normalize_suite_ids(suite_ids)

    if fallback_input and fallback_input.strip():
        return normalize_suite_ids(fallback_input)

    return fetch_all_suite_ids(session, headers, org, project, plan_id)


def normalize_suite_ids(suite_ids: Any) -> List[int]:
    if isinstance(suite_ids, int):
        return [suite_ids]

    if isinstance(suite_ids, str):
        return [int(x.strip()) for x in suite_ids.split(",") if x.strip()]

    return list(suite_ids)


def fetch_child_suite_ids(
    session: requests.Session,
    headers: Dict[str, str],
    org: str,
    project: str,
    plan_id: str,
    suite_id: int,
) -> List[int]:
    """Return direct child suite IDs, or an empty list if discovery fails."""
    suite_url = (
        f"https://dev.azure.com/{org}/{project}"
        f"/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}"
    )
    data, error = fetch_json(
        session,
        suite_url,
        headers,
        params={"expand": "Children", "api-version": "7.1"},
    )

    if error:
        print(f"Unable to discover children for Suite {suite_id}: {error}")
        return []

    child_ids = []
    for child in data.get("children") or []:
        child_id = child.get("id") if isinstance(child, dict) else None
        if child_id is None:
            continue
        try:
            child_ids.append(int(child_id))
        except (TypeError, ValueError):
            print(f"Ignoring invalid child suite ID under Suite {suite_id}: {child_id!r}")

    return child_ids


def collect_suite_ids(
    session: requests.Session,
    headers: Dict[str, str],
    org: str,
    project: str,
    plan_id: str,
    root_suite_ids: List[int],
) -> List[int]:
    """Collect roots and all descendants in deterministic depth-first order."""
    collected = []
    visited = set()
    pending = list(reversed(root_suite_ids))

    while pending:
        suite_id = pending.pop()
        suite_key = str(suite_id)
        if suite_key in visited:
            continue

        visited.add(suite_key)
        collected.append(suite_id)
        child_ids = fetch_child_suite_ids(
            session, headers, org, project, plan_id, suite_id
        )
        pending.extend(reversed(child_ids))

    return collected



def current_tester_from_point(point: Dict[str, Any]) -> Any:
    """Return the tester exactly as the existing record builder would."""
    assigned = point.get("assignedTo", {})
    if isinstance(assigned, dict):
        return assigned.get("displayName", "Unassigned")
    return assigned


def is_assigned_tester(tester: Any) -> bool:
    """Return whether a tester value represents an assigned identity."""
    if tester is None:
        return False
    normalized = str(tester).strip()
    return bool(normalized) and normalized.casefold() != "unassigned"


def needs_tester_fallback(point: Dict[str, Any]) -> bool:
    """Return whether this point is eligible for a Test Result lookup."""
    outcome = str(point.get("outcome", "Not Run")).strip()
    return (
        outcome.casefold() == "passed"
        and not is_assigned_tester(current_tester_from_point(point))
    )


def fetch_test_result_executor(
    session: requests.Session,
    headers: Dict[str, str],
    org: str,
    project: str,
    run_id: str,
    result_id: str,
) -> Optional[str]:
    """Fetch the identity in TestCaseResult.runBy."""
    result_url = (
        f"https://dev.azure.com/{org}/{project}"
        f"/_apis/test/Runs/{run_id}/results/{result_id}"
    )
    data, error = fetch_json(
        session,
        result_url,
        headers,
        params={"api-version": API_VERSION},
    )

    if error:
        print(
            f"Unable to resolve tester for Run {run_id}, "
            f"Result {result_id}: {error}"
        )
        return None

    run_by = data.get("runBy") if isinstance(data, dict) else None
    if not isinstance(run_by, dict):
        return None

    executor = run_by.get("displayName") or run_by.get("uniqueName")
    return str(executor).strip() if executor else None


def resolve_current_tester(
    session: requests.Session,
    headers: Dict[str, str],
    org: str,
    project: str,
    point: Dict[str, Any],
) -> Any:
    """Use TestCaseResult.runBy only for a passed, unassigned test point."""
    current_tester = current_tester_from_point(point)
    if not needs_tester_fallback(point):
        return current_tester

    run_id, result_id = extract_run_result_ids(point)
    if not run_id or not result_id:
        return current_tester

    executor = fetch_test_result_executor(
        session, headers, org, project, run_id, result_id
    )
    return executor if is_assigned_tester(executor) else current_tester


def fetch_points_for_suite(session: requests.Session, headers: Dict[str, str], org: str, project: str, plan_id: str, suite_id: int) -> List[Dict[str, Any]]:
    points = []
    skip = 0

    while True:
        url = (
            f"https://dev.azure.com/{org}/{project}"
            f"/_apis/test/Plans/{plan_id}/Suites/{suite_id}/points"
        )

        page, error = fetch_json(
            session,
            url,
            headers,
            params={
                "includePointDetails": "true",
                "$skip": skip,
                "$top": POINT_PAGE_SIZE,
                "api-version": API_VERSION,
            },
        )
        if error:
            print(f"Skipping Suite {suite_id}: {error}")
            return []

        page = page.get("value", [])

        points.extend(page)

        if len(page) < POINT_PAGE_SIZE:
            return points

        skip += len(page)


def fetch_test_points(
    project: str,
    plan_id: str,
    suite_ids: Optional[Any] = None,
    pat: Optional[str] = None,
    suite_ids_input: str = "",
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    validate_environment(project, plan_id, pat)

    print("environment is validated")

    session = create_session(pat)
    headers = {"Accept": "application/json"}

    root_suite_ids = resolve_suite_ids(
        suite_ids, suite_ids_input, session, headers, ORG, project, plan_id
    )
    print("resolved suite ids")
    resolved_suite_ids = collect_suite_ids(
        session, headers, ORG, project, plan_id, root_suite_ids
    )
    print("collected suite ids")
    total_suites = len(resolved_suite_ids)
    if progress_callback:
        progress_callback(0, total_suites)
    records = []
    seen_test_case_ids = set()

    for suite_index, suite_id in enumerate(resolved_suite_ids, start=1):
        print(f"Fetching Suite {suite_id}")
        points = fetch_points_for_suite(
            session, headers, ORG, project, plan_id, suite_id
        )

        unique_points = []
        for point in points:
            test_case = point.get("testCase") or {}
            test_case_id = test_case.get("id") if isinstance(test_case, dict) else None
            if test_case_id is not None:
                deduplication_key = str(test_case_id)
                if deduplication_key in seen_test_case_ids:
                    continue
                seen_test_case_ids.add(deduplication_key)
            unique_points.append(point)

        attachments = [None] * len(unique_points)
        resolved_testers = [
            current_tester_from_point(point) for point in unique_points
        ]

        from concurrent.futures import ThreadPoolExecutor, as_completed
        from evidenceiq.services.evidence_service import fetch_attachment_details

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {
                executor.submit(fetch_attachment_details, session, headers, ORG, project, point): index
                for index, point in enumerate(unique_points)
            }
            tester_future_map = {
                executor.submit(
                    resolve_current_tester,
                    session,
                    headers,
                    ORG,
                    project,
                    point,
                ): index
                for index, point in enumerate(unique_points)
                if needs_tester_fallback(point)
            }

            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    attachments[index] = future.result()
                except Exception as exc:
                    attachments[index] = evidence_response("Error", error=f"Unexpected attachment lookup error: {exc}")

            for future in as_completed(tester_future_map):
                index = tester_future_map[future]
                try:
                    resolved_testers[index] = future.result()
                except Exception as exc:
                    print(
                        f"Unexpected tester lookup error for point "
                        f"{unique_points[index].get('id', 'N/A')}: {exc}"
                    )

        from evidenceiq.processing.transformers import build_record

        resolved_points = []
        for point, resolved_tester in zip(unique_points, resolved_testers):
            current_tester = current_tester_from_point(point)
            if (
                resolved_tester != current_tester
                and is_assigned_tester(resolved_tester)
            ):
                point = dict(point)
                point["assignedTo"] = {"displayName": resolved_tester}
            resolved_points.append(point)

        for point, attachment in zip(resolved_points, attachments):
            records.append(build_record(suite_id, point, attachment))

        if progress_callback:
            progress_callback(suite_index, total_suites)

    return build_dataframe(records)


# def fetch_paycode(org: str, project: str, test_case_id: int):
#     session = create_session(pat)
#     headers = {"Accept": "application/json"}
#     url = (
#     f"https://dev.azure.com/{org}/{project}"
#     f"/_apis/wit/workitems/{test_case_id}"
#     f"?api-version=7.1"
# )

#     try:
#         response = session.get(url, headers=headers, timeout=30)
#         response.raise_for_status()
#         data = response.json()

#         steps_xml = data["fields"].get("Microsoft.VSTS.TCM.Steps", "")
#         root = ET.fromstring(steps_xml)

#         root = ET.fromstring(steps_xml)

#         all_steps = root.findall("step")

#         if all_steps:
#             last_step = all_steps[-1]
#             values = last_step.findall("parameterizedString")

#             last_expected = values[1].text.strip() if len(values) > 1 and values[1].text else ""

#         return last_expected

#     except requests.RequestException as exc:
#         return None, response_error_message(exc)
#     except ValueError as exc:
#         return None, f"Invalid JSON response: {exc}"


# if __name__ == "__main__":
#     project = "EUROPE_SFA"
#     plan_id = "99859"
#     suite_ids = 171093
#     pat = None

#     paycode = fetch_test_points(project, plan_id, suite_ids, pat)
#     print(paycode)

