"""Export and formatting helpers for reports."""

from typing import Any

import pandas as pd



def build_csv_data(df: pd.DataFrame) -> str:
    return df.to_csv(index=False)


def filter_dataframe(df: pd.DataFrame, outcomes: Any, testers: Any, search: str) -> pd.DataFrame:
    if df.empty:
        return df

    filtered = df.copy()

    if "Outcome" in df.columns and outcomes:
        filtered = filtered[filtered["Outcome"].isin(outcomes)]

    if "Run By" in df.columns and testers:
        filtered = filtered[filtered["Run By"].isin(testers)]

    if search and "Test Case Name" in df.columns:
        search_value = str(search).strip().lower()
        if search_value:
            filtered = filtered[
                filtered["Test Case Name"].fillna("").astype(str).apply(lambda value: search_value in value.lower())
            ]

    return filtered
