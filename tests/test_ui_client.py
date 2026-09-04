from unittest.mock import Mock

from frontend.ui.app import fetch_dashboard


def test_fetch_dashboard_posts_form_values_to_backend(monkeypatch):
    submit_response = Mock()
    submit_response.ok = True
    submit_response.json.return_value = {"job_id": "job-1", "status": "queued"}
    status_response = Mock()
    status_response.ok = True
    status_response.json.return_value = {
        "job_id": "job-1", "status": "completed", "error": None
    }
    result_response = Mock()
    result_response.ok = True
    result_response.json.return_value = {"records": [], "metrics": {"total": 0}}
    post = Mock(return_value=submit_response)
    get = Mock(side_effect=[status_response, result_response])
    monkeypatch.setattr("frontend.ui.app.requests.post", post)
    monkeypatch.setattr("frontend.ui.app.requests.get", get)

    payload = fetch_dashboard("Demo", "123", "10,11")

    assert payload["records"] == []
    post.assert_called_once_with(
        "http://127.0.0.1:8000/dashboard/jobs",
        json={"project": "Demo", "plan_id": "123", "suite_ids": "10,11"},
        timeout=15,
    )
    assert get.call_args_list[0].args[0].endswith("/dashboard/jobs/job-1")
    assert get.call_args_list[1].args[0].endswith("/dashboard/jobs/job-1/result")
