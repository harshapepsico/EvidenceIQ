from unittest.mock import Mock

from evidenceiq.ui.app import fetch_dashboard


def test_fetch_dashboard_posts_form_values_to_backend(monkeypatch):
    response = Mock()
    response.ok = True
    response.json.return_value = {"records": [], "metrics": {"total": 0}}
    post = Mock(return_value=response)
    monkeypatch.setattr("evidenceiq.ui.app.requests.post", post)

    payload = fetch_dashboard("Demo", "123", "10,11")

    assert payload["records"] == []
    post.assert_called_once_with(
        "http://127.0.0.1:8000/dashboard/load",
        json={"project": "Demo", "plan_id": "123", "suite_ids": "10,11"},
        timeout=300,
    )
