import requests

from evidenceiq.services import ado_service


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self.payload = payload or {}
        self.headers = headers or {}
        self.text = text
        self.reason = "Too Many Requests" if status_code == 429 else "Error"

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_fetch_json_honors_retry_after(monkeypatch):
    session = FakeSession(
        [
            FakeResponse(429, headers={"Retry-After": "3"}),
            FakeResponse(200, {"value": [1]}),
        ]
    )
    delays = []
    monkeypatch.setattr(ado_service, "ADO_MAX_RETRIES", 1)
    monkeypatch.setattr(ado_service.time, "sleep", delays.append)

    data, error = ado_service.fetch_json(session, "https://ado/test", {})

    assert data == {"value": [1]}
    assert error == ""
    assert delays == [3.0]
    assert len(session.calls) == 2


def test_fetch_json_retries_transient_server_error_with_backoff(monkeypatch):
    session = FakeSession(
        [FakeResponse(503, text="temporarily unavailable"), FakeResponse(200, {"ok": True})]
    )
    delays = []
    monkeypatch.setattr(ado_service, "ADO_MAX_RETRIES", 1)
    monkeypatch.setattr(ado_service, "ADO_BACKOFF_SECONDS", 2)
    monkeypatch.setattr(ado_service.random, "uniform", lambda start, end: 0)
    monkeypatch.setattr(ado_service.time, "sleep", delays.append)

    data, error = ado_service.fetch_json(session, "https://ado/test", {})

    assert data == {"ok": True}
    assert error == ""
    assert delays == [2]


def test_fetch_points_for_suite_preserves_pagination(monkeypatch):
    monkeypatch.setattr(ado_service, "POINT_PAGE_SIZE", 2)
    session = FakeSession(
        [
            FakeResponse(200, {"value": [{"id": 1}, {"id": 2}]}),
            FakeResponse(200, {"value": [{"id": 3}]}),
        ]
    )

    points = ado_service.fetch_points_for_suite(
        session, {}, "org", "project", "plan", 10
    )

    assert points == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert [call[1]["params"]["$skip"] for call in session.calls] == [0, 2]


def test_fetch_all_suite_ids_follows_continuation_header():
    session = FakeSession(
        [
            FakeResponse(
                200,
                {"value": [{"id": 10}]},
                headers={"x-ms-continuationtoken": "next-page"},
            ),
            FakeResponse(200, {"value": [{"id": 11}]}),
        ]
    )

    suite_ids = ado_service.fetch_all_suite_ids(
        session, {}, "org", "project", "plan"
    )

    assert suite_ids == [10, 11]
    assert session.calls[1][1]["params"]["continuationToken"] == "next-page"


def test_fetch_json_does_not_retry_client_errors(monkeypatch):
    session = FakeSession([FakeResponse(401, text="unauthorized")])
    monkeypatch.setattr(ado_service, "ADO_MAX_RETRIES", 4)
    delays = []
    monkeypatch.setattr(ado_service.time, "sleep", delays.append)

    data, error = ado_service.fetch_json(session, "https://ado/test", {})

    assert data is None
    assert "401" in error
    assert delays == []
    assert len(session.calls) == 1


def test_fetch_points_for_suite_skips_after_retry_exhaustion(monkeypatch, capsys):
    session = FakeSession([FakeResponse(429, text="rate limited")])
    monkeypatch.setattr(ado_service, "ADO_MAX_RETRIES", 0)

    points = ado_service.fetch_points_for_suite(
        session, {}, "org", "project", "plan", 10
    )

    assert points == []
    assert "Skipping Suite 10" in capsys.readouterr().out
