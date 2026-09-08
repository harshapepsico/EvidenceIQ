import pandas as pd
from fastapi.testclient import TestClient

from backend.app import _request_key, app, load_dashboard
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
        DashboardRequest(project=" Demo ", plan_id=" 123 ", suite_ids="1,2", pat="secret")
    )

    assert captured == {
        "project": "Demo",
        "plan_id": "123",
        "suite_ids": None,
        "pat": "secret",
        "suite_ids_input": "1,2",
    }
    assert len(response.records) == 2
    assert response.metrics["total"] == 2
    assert response.metrics["passed"] == 1


def test_dashboard_request_requires_pat():
    response = TestClient(app).post(
        "/dashboard/load",
        json={"project": "Demo", "plan_id": "123", "suite_ids": None},
    )

    assert response.status_code == 422


def test_pat_is_hashed_in_request_key():
    first = DashboardRequest(project="Demo", plan_id="123", pat="secret")
    second = DashboardRequest(project="Demo", plan_id="123", pat="different")

    assert "secret" not in _request_key(first)
    assert _request_key(first) != _request_key(second)


def test_load_dashboard_serializes_missing_values_as_null(monkeypatch):
    dataframe = pd.DataFrame([{"Outcome": "Passed", "Run By": None}])
    monkeypatch.setattr("backend.app.fetch_test_points", lambda **kwargs: dataframe)

    response = load_dashboard(DashboardRequest(project="Demo", plan_id="123", pat="secret"))

    assert response.records[0]["Run By"] is None


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
        json={"project": "Demo", "plan_id": "123", "suite_ids": None, "pat": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["metrics"]["not_run"] == 1


def test_dashboard_job_reuses_completed_result(monkeypatch):
    dataframe = pd.DataFrame([{"Outcome": "Passed"}])
    fetch = lambda **kwargs: dataframe
    monkeypatch.setattr("backend.app.fetch_test_points", fetch)

    request = {"project": "CacheDemo", "plan_id": "123", "suite_ids": "10", "pat": "secret"}
    client = TestClient(app)
    first = client.post("/dashboard/jobs", json=request)
    assert first.status_code == 202
    first_job_id = first.json()["job_id"]

    status_response = client.get(f"/dashboard/jobs/{first_job_id}")
    for _ in range(20):
        if status_response.json()["status"] == "completed":
            break
        status_response = client.get(f"/dashboard/jobs/{first_job_id}")

    assert status_response.json()["status"] == "completed"
    second = client.post("/dashboard/jobs", json=request)

    assert second.status_code == 202
    assert second.json() == {"job_id": first_job_id, "status": "completed"}
    result = client.get(f"/dashboard/jobs/{first_job_id}/result")
    assert result.json()["records"] == [{"Outcome": "Passed"}]
