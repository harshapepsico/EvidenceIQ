"""Sidebar rendering helpers."""

import streamlit as st


def render_sidebar_inputs():
    """Render the project, plan, suite, and load controls."""
    project = st.sidebar.text_input("Project Name")
    plan_id = st.sidebar.text_input("Test Plan ID")
    suite_ids_input = st.sidebar.text_input(
        "Suite IDs (optional)",
        placeholder="12345,67890",
    )
    load_clicked = st.sidebar.button(
        "🚀 Load Dashboard",
        type="primary",
        use_container_width=True,
    )
    return project, plan_id, suite_ids_input, load_clicked


def render_filter_controls(df):
    """Render dashboard filter widgets in the sidebar."""
    st.sidebar.header("Filters")

    outcome_column = "Outcome" if "Outcome" in df.columns else None
    tester_column = "Run By" if "Run By" in df.columns else None

    outcome_values = []
    tester_values = []

    if outcome_column:
        outcome_values = sorted(df[outcome_column].dropna().astype(str).unique())

    if tester_column:
        tester_values = sorted(df[tester_column].dropna().astype(str).unique())

    outcomes = st.sidebar.multiselect(
        "Outcome",
        outcome_values,
        default=outcome_values,
    )

    testers = st.sidebar.multiselect(
        "Run By",
        tester_values,
        default=tester_values,
    )

    search = st.sidebar.text_input("Search Test Case")
    return outcomes, testers, search
