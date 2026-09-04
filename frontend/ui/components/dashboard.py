"""Dashboard rendering helpers."""

import pandas as pd
import plotly.express as px
import streamlit as st


def render_dashboard(df: pd.DataFrame, filtered: pd.DataFrame, metrics: dict) -> None:
    """Render KPI cards, charts, and the main data table."""
    st.subheader("Execution Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Test Cases", metrics["total"])
    c2.metric("Passed", metrics["passed"])
    c3.metric("Failed", metrics["failed"])
    c4.metric("Blocked", metrics["blocked"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Not Run", metrics["not_run"])
    c6.metric("Pass Rate", f"{metrics['pass_rate']}%")
    c7.metric("Fail Rate", f"{metrics['fail_rate']}%")
    c8.metric("Evidence Compliance", f"{metrics['evidence_compliance']:.2f}%")

    c9 = st.columns(1)[0]
    c9.metric("Run Rate", f"{metrics['execution_rate']}%")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Outcome Distribution")
        if "Outcome" in df.columns:
            outcome_df = df.groupby("Outcome").size().reset_index(name="Count")
            fig = px.pie(outcome_df, names="Outcome", values="Count", hole=0.45)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Outcome data is not available yet.")

    with right:
        st.subheader("Tester Distribution")
        if "Run By" in df.columns:
            tester_df = df.groupby("Run By").size().reset_index(name="Count")
            fig = px.bar(tester_df, x="Run By", y="Count", color="Count")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Tester data is not available yet.")

    st.divider()
    st.subheader("Test Cases")
    if df.empty:
        st.info("No test cases match the current filters.")
    else:
        st.dataframe(df)

    st.download_button(
        label="📥 Download CSV",
        data=filtered.to_csv(index=False),
        file_name="ado_test_cases.csv",
        mime="text/csv",
    )
