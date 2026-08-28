import pandas as pd
from fastapi.testclient import TestClient

from backend.app import app, load_dashboard
from backend.schemas import DashboardRequest


def test_load_dashboard_returns_records_and_metrics(monkeypatch):
    dataframe = pd.DataFrame(
        [
            {"Outcome": "Passed", "Evidence Uploaded": "Yes"},
            {"Outcome": "Failed", "Evidence Uploaded": "No"},
        ]
    )
    captured = {}

    def fake_fetch_test_points(**kwargs):
        captured.update(kwargs)
        return dataframe

    monkeypatch.setattr("backend.app.fetch_test_points", fake_fetch_test_points)

    response = load_dashboard(
        DashboardRequest(project=" Demo ", plan_id=" 123 ", suite_ids="1,2")
    )

    assert captured == {
        "project": "Demo",
        "plan_id": "123",
        "suite_ids": None,
        "pat": None,
        "suite_ids_input": "1,2",
    }
    assert len(response.records) == 2
    assert response.metrics["total"] == 2
    assert response.metrics["passed"] == 1


def test_load_dashboard_serializes_missing_values_as_null(monkeypatch):
    dataframe = pd.DataFrame([{"Outcome": "Passed", "Current Tester": None}])
    monkeypatch.setattr("backend.app.fetch_test_points", lambda **kwargs: dataframe)

    response = load_dashboard(DashboardRequest(project="Demo", plan_id="123"))

    assert response.records[0]["Current Tester"] is None


def test_dashboard_post_route(monkeypatch):
    dataframe = pd.DataFrame(
        [{"Outcome": "Not Run", "Evidence Uploaded": "N/A"}]
    )
    monkeypatch.setattr(
        "backend.app.fetch_test_points",
        lambda **kwargs: dataframe,
    )

    response = TestClient(app).post(
        "/dashboard/load",
        json={"project": "Demo", "plan_id": "123", "suite_ids": None},
    )

    assert response.status_code == 200
    assert response.json()["metrics"]["not_run"] == 1
