"""Streamlit client for the EvidenceIQ FastAPI backend."""

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Streamlit adds this script's directory to the import path. Add the repository
# root as well so the evidenceiq package can be imported from a direct run.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
import streamlit as st

from evidenceiq.ui.components.sidebar import render_sidebar_inputs

DEFAULT_API_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT_SECONDS = 300
JOB_REQUEST_TIMEOUT_SECONDS = 15
JOB_POLL_INTERVAL_SECONDS = 2
JOB_POLL_TIMEOUT_SECONDS = 1800


def _error_detail(response: requests.Response) -> str:
    """Extract a readable error returned by FastAPI."""
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"Backend returned HTTP {response.status_code}."

    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, list):
        return "; ".join(
            str(item.get("msg", item)) if isinstance(item, dict) else str(item)
            for item in detail
        )
    return str(detail or payload)


def fetch_dashboard(
    project: str,
    plan_id: str,
    suite_ids: str,
    progress_callback=None,
) -> Dict[str, Any]:
    """Submit a dashboard job and poll until its cached result is ready."""
    api_url = os.getenv("EVIDENCEIQ_API_URL", DEFAULT_API_URL).rstrip("/")
    response = requests.post(
        f"{api_url}/dashboard/jobs",
        json={
            "project": project,
            "plan_id": plan_id,
            "suite_ids": suite_ids or None,
        },
        timeout=JOB_REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise RuntimeError(_error_detail(response))

    job_id = response.json()["job_id"]
    deadline = time.monotonic() + JOB_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status_response = requests.get(
            f"{api_url}/dashboard/jobs/{job_id}",
            timeout=JOB_REQUEST_TIMEOUT_SECONDS,
        )
        if not status_response.ok:
            raise RuntimeError(_error_detail(status_response))
        job = status_response.json()
        if progress_callback:
            progress_callback(
                job.get("progress", 0),
                job.get("completed_suites", 0),
                job.get("total_suites", 0),
            )
        if job["status"] == "completed":
            result_response = requests.get(
                f"{api_url}/dashboard/jobs/{job_id}/result",
                timeout=JOB_REQUEST_TIMEOUT_SECONDS,
            )
            if not result_response.ok:
                raise RuntimeError(_error_detail(result_response))
            return result_response.json()
        if job["status"] == "failed":
            raise RuntimeError(job.get("error") or "Dashboard job failed.")
        time.sleep(JOB_POLL_INTERVAL_SECONDS)

    raise TimeoutError("Dashboard is still loading. Please try again shortly.")


def render_loaded_dashboard(records) -> None:
    """Load and render dashboard dependencies only after the API succeeds."""
    import pandas as pd

    from evidenceiq.processing.metrics import calculate_metrics
    from evidenceiq.processing.reports import filter_dataframe
    from evidenceiq.ui.components.dashboard import render_dashboard
    from evidenceiq.ui.components.sidebar import render_filter_controls

    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        st.warning("No test cases found.")
        return

    outcomes, testers, search = render_filter_controls(dataframe)
    filtered = filter_dataframe(dataframe, outcomes, testers, search)
    metrics = calculate_metrics(filtered)

    render_dashboard(filtered, filtered, metrics)


def run_app() -> None:
    """Render the dashboard and load its data through FastAPI."""
    st.set_page_config(
        page_title="ADO WFM QA Dashboard",
        page_icon="🧪",
        layout="wide",
    )
    st.title("🧪 ADO WFM QA Dashboard")

    if "dashboard_loaded" not in st.session_state:
        st.session_state.dashboard_loaded = False
    if "records" not in st.session_state:
        st.session_state.records = None

    project, plan_id, suite_ids_input, load_clicked = render_sidebar_inputs()

    if load_clicked:
        if not project.strip() or not plan_id.strip():
            st.sidebar.error("Project Name and Test Plan ID are required.")
        else:
            with st.spinner("Fetching test cases from Azure DevOps..."):
                try:
                    progress_bar = st.progress(0, text="Starting dashboard load...")

                    def update_progress(percentage, completed, total):
                        label = (
                            f"Fetching suites: {completed}/{total} completed ({percentage}%)"
                            if total
                            else "Discovering test suites..."
                        )
                        progress_bar.progress(percentage, text=label)

                    payload = fetch_dashboard(
                        project, plan_id, suite_ids_input, update_progress
                    )
                    progress_bar.progress(100, text="Dashboard ready (100%)")
                except (requests.RequestException, TimeoutError) as exc:
                    st.error(
                        "Could not reach the EvidenceIQ backend. "
                        f"Make sure it is running at the configured URL. ({exc})"
                    )
                except (RuntimeError, ValueError) as exc:
                    st.error(f"Unable to load dashboard: {exc}")
                else:
                    st.session_state.records = payload.get("records", [])
                    st.session_state.dashboard_loaded = True

    if not st.session_state.dashboard_loaded:
        st.info("Please enter Project and Test Plan ID.")
        return

    render_loaded_dashboard(st.session_state.records)


if __name__ == "__main__":
    run_app()
