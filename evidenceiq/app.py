"""Application composition root for the refactored EvidenceIQ app."""

import pandas as pd
import streamlit as st

from evidenceiq.frontend.components.chat import render_chat
from evidenceiq.frontend.components.dashboard import render_dashboard
from evidenceiq.frontend.components.sidebar import render_filter_controls, render_sidebar_inputs
from evidenceiq.processing.metrics import calculate_metrics
from evidenceiq.processing.reports import filter_dataframe
from evidenceiq.services.ado_service3 import fetch_test_points


def run_app() -> None:
    """Run the Streamlit dashboard with the new package structure."""
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
        with st.spinner("Fetching test cases from Azure DevOps..."):
            st.session_state.records = fetch_test_points(
                project=project,
                plan_id=plan_id,
                suite_ids=None,
                pat=None,
                suite_ids_input=suite_ids_input,
            )
            st.session_state.dashboard_loaded = True

    if not st.session_state.dashboard_loaded:
        st.info("Please enter Project and Test Plan ID.")
        st.stop()

    records = st.session_state.records
    df = pd.DataFrame(records)

    if df.empty:
        st.warning("No test cases found.")
        st.stop()

    outcomes, testers, search = render_filter_controls(df)
    filtered = filter_dataframe(df, outcomes, testers, search)
    metrics = calculate_metrics(filtered)

    render_dashboard(filtered, filtered, metrics)
    render_chat(df)


if __name__ == "__main__":
    run_app()
