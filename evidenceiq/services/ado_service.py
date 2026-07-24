"""Azure DevOps service layer."""

import os
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
import xml

import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

from evidenceiq.config.settings import API_VERSION, ORG, POINT_PAGE_SIZE, get_pat
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


def fetch_json(session: requests.Session, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None):
    try:
        response = session.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json(), ""
    
    except requests.RequestException as exc:
        return None, response_error_message(exc)
    except ValueError as exc:
        return None, f"Invalid JSON response: {exc}"


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
    
    #print(data)

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

    #print(data)

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

    response = session.get(suites_url, headers=headers, timeout=30)
    response.raise_for_status()
    #print(response)

    suites = response.json().get("value", [])
    suite_ids = [suite["id"] for suite in suites]
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


def fetch_points_for_suite(session: requests.Session, headers: Dict[str, str], org: str, project: str, plan_id: str, suite_id: int) -> List[Dict[str, Any]]:
    points = []
    skip = 0

    while True:
        url = (
            f"https://dev.azure.com/{org}/{project}"
            f"/_apis/test/Plans/{plan_id}/Suites/{suite_id}/points"
        )

        response = session.get(
            url,
            headers=headers,
            params={
                "includePointDetails": "true",
                "$skip": skip,
                "$top": POINT_PAGE_SIZE,
                "api-version": API_VERSION,
            },
            timeout=30,
        )

        #print(response)

        if response.status_code != 200:
            body = response.text.replace("\n", " ").strip()[:300]
            message = f"Skipping Suite {suite_id}: {response.status_code}"
            if body:
                message = f"{message} - {body}"
            print(message)
            return []

        page = response.json().get("value", [])
        #print(page)
        points.extend(page)
        #print(points)
        #print()

        if len(page) < POINT_PAGE_SIZE:
            return points

        skip += len(page)


def fetch_test_points(project: str, plan_id: str, suite_ids: Optional[Any] = None, pat: Optional[str] = None, suite_ids_input: str = "") -> pd.DataFrame:
    validate_environment(project, plan_id, pat)

    session = create_session(pat)
    headers = {"Accept": "application/json"}

    resolved_suite_ids = resolve_suite_ids(suite_ids, suite_ids_input, session, headers, ORG, project, plan_id)
    records = []

    for suite_id in resolved_suite_ids:
        print(f"Fetching Suite {suite_id}")
        points = fetch_points_for_suite(session, headers, ORG, project, plan_id, suite_id)
        #print(f"Fetched {len(points)} points for Suite {suite_id}")
        attachments = [None] * len(points)

        from concurrent.futures import ThreadPoolExecutor, as_completed
        from evidenceiq.services.evidence_service import fetch_attachment_details

        with ThreadPoolExecutor(max_workers=min(20, os.cpu_count() * 4 if os.cpu_count() else 4)) as executor:
            future_map = {
                executor.submit(fetch_attachment_details, session, headers, ORG, project, point): index
                for index, point in enumerate(points)
            }

            #print(future_map)

            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    attachments[index] = future.result()
                except Exception as exc:
                    attachments[index] = evidence_response("Error", error=f"Unexpected attachment lookup error: {exc}")

        from evidenceiq.processing.transformers import build_record

        for point, attachment in zip(points, attachments):
            records.append(build_record(suite_id, point, attachment))

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

#             #print(last_expected)

#         return last_expected
    
#     except requests.RequestException as exc:
#         return None, response_error_message(exc)
#     except ValueError as exc:
#         return None, f"Invalid JSON response: {exc}"

if __name__ == "__main__":
    # Example usage
    project = "EUROPE_SFA"
    plan_id = "99859"
    suite_ids = 171093# or provide a list of suite IDs
    pat = None  # or provide your Personal Access Token

    paycode = fetch_test_points(project, plan_id, suite_ids, pat)
    print(paycode)