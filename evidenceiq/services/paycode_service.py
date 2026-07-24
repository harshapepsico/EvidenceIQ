
import os
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
import xml

import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from evidenceiq.config.settings import API_VERSION, ORG, POINT_PAGE_SIZE, get_pat
from evidenceiq.utils.helpers import extract_run_result_ids, response_error_message
from evidenceiq.services.ado_service import create_session


def fetch_paycode(org: str, project: str, test_case_id: int):
    pat = None
    session = create_session(pat)
    headers = {"Accept": "application/json"}
    url = (
    f"https://dev.azure.com/{org}/{project}"
    f"/_apis/wit/workitems/{test_case_id}"
    f"?api-version=7.1"
    )

    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        steps_xml = data["fields"].get("Microsoft.VSTS.TCM.Steps", "")
        root = ET.fromstring(steps_xml)

        root = ET.fromstring(steps_xml)

        all_steps = root.findall("step")

        if all_steps:
            last_step = all_steps[-1]
            values = last_step.findall("parameterizedString")

            last_expected = values[1].text.strip() if len(values) > 1 and values[1].text else ""

            #print(last_expected)

        return last_expected
    
    except requests.RequestException as exc:
        return None, response_error_message(exc)
    except ValueError as exc:
        return None, f"Invalid JSON response: {exc}"
    
def fetch_paycode_name(ORG, project, test_case_id):
    text = fetch_paycode(ORG, project, test_case_id)

    paycodes = [
    "Regular Time",
    "Overtime",
    "Doubletime",
    "Hours Differential",
    ]
    result = ""
    for paycode in paycodes:
        if paycode in text:
            result += paycode + " | "
    
    return result.strip(" | ")

if __name__ == "__main__":
    #example usage
    ORG = "PepsiCoIT"
    project = "WFM_Program"
    test_case_id = 26457274 # Replace with a valid test case ID

    paycode_name = fetch_paycode_name(ORG, project, test_case_id)
    print(f"Paycode Name: {paycode_name}")
