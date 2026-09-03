import io
import logging
import zipfile

from evidenceiq.services import ado_service, evidence_service


class FakeDownloadResponse:
    def __init__(self, content=b"evidence", content_type="application/octet-stream"):
        self.content = content
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        return None


class FakeDownloadSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses[url]


def passed_point():
    return {
        "id": 42,
        "outcome": "Passed",
        "lastTestRun": {"id": 10},
        "lastResult": {"id": 20},
    }


def result_download_url(attachment_id):
    return (
        "https://dev.azure.com/org/project"
        f"/_apis/test/Runs/10/Results/20/attachments/{attachment_id}"
    )


def iteration_download_url(attachment_id):
    return (
        "https://vstmr.dev.azure.com/org/project"
        f"/_apis/testresults/runs/10/results/20/attachments/{attachment_id}"
    )


def test_fetch_attachment_details_ocrs_all_unique_sources_and_prints_content(
    monkeypatch,
    capsys,
):
    result_attachments = [
        {"id": 1, "fileName": "result.pdf", "url": "https://ado/a", "size": 10},
        {"id": 2, "fileName": "image.png", "url": "https://ado/b", "size": 10},
    ]
    iteration_attachments = [
        {
            "id": 3,
            "iterationId": 1,
            "name": "action.txt",
            "url": "https://ado/collection",
            "size": 10,
        },
        {
            "id": 3,
            "iterationId": 1,
            "name": "action.txt",
            "url": "https://ado/collection",
            "size": 10,
        },
    ]
    monkeypatch.setattr(
        evidence_service,
        "fetch_result_attachments",
        lambda *args: (result_attachments, ""),
    )
    monkeypatch.setattr(
        evidence_service,
        "fetch_iteration_attachments",
        lambda *args: (iteration_attachments, ""),
    )

    ocr_calls = []

    def fake_ocr(file_name, file_bytes, model_name):
        ocr_calls.append((file_name, file_bytes, model_name))
        return {"data": {"content": f"content for {file_name}"}}

    monkeypatch.setattr(evidence_service, "extract_bytes_via_stream", fake_ocr)
    session = FakeDownloadSession(
        {
            result_download_url(1): FakeDownloadResponse(b"result bytes"),
            result_download_url(2): FakeDownloadResponse(b"image bytes"),
            iteration_download_url(3): FakeDownloadResponse(b"action bytes"),
        }
    )

    response = evidence_service.fetch_attachment_details(
        session,
        {"Accept": "application/json"},
        "org",
        "project",
        passed_point(),
    )

    assert response["Evidence Uploaded"] == "Yes"
    assert response["Evidence Count"] == 3
    assert len(session.calls) == 3
    assert session.calls[2][1]["params"] == {
        "iterationId": "1",
        "api-version": "7.1-preview.1",
    }
    assert ocr_calls == [
        ("result.pdf", b"result bytes", "prebuilt-layout"),
        ("image.png", b"image bytes", "prebuilt-layout"),
        ("action.txt", b"action bytes", "prebuilt-layout"),
    ]
    output = capsys.readouterr().out
    assert "Test Point ID: 42" in output
    assert "content for result.pdf" in output
    assert "content for action.txt" in output
    assert "OCR" not in response


def test_zip_wrapped_download_is_unpacked_before_ocr(monkeypatch):
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("folder/evidence.pdf", b"original PDF bytes")

    attachment = {
        "id": 1,
        "fileName": "evidence.pdf",
        "url": "https://ado/zip",
        "size": 100,
    }
    monkeypatch.setattr(
        evidence_service,
        "fetch_result_attachments",
        lambda *args: ([attachment], ""),
    )
    monkeypatch.setattr(
        evidence_service,
        "fetch_iteration_attachments",
        lambda *args: ([], ""),
    )
    calls = []
    monkeypatch.setattr(
        evidence_service,
        "extract_bytes_via_stream",
        lambda *args: calls.append(args) or {"data": {"content": "text"}},
    )
    session = FakeDownloadSession(
        {
            result_download_url(1): FakeDownloadResponse(
                archive_bytes.getvalue(),
                "application/zip",
            )
        }
    )

    evidence_service.fetch_attachment_details(
        session,
        {},
        "org",
        "project",
        passed_point(),
    )

    assert calls == [("evidence.pdf", b"original PDF bytes", "prebuilt-layout")]


def test_octet_stream_zip_wrapper_is_detected(monkeypatch):
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("evidence.pdf", b"wrapped bytes")

    files = evidence_service._files_from_download(
        "evidence.pdf",
        archive_bytes.getvalue(),
        "application/octet-stream",
    )

    assert files == [("evidence.pdf", b"wrapped bytes")]


def test_oversized_attachment_is_skipped_without_download(monkeypatch, caplog):
    attachment = {
        "id": 1,
        "fileName": "large.pdf",
        "url": "https://ado/large",
        "size": evidence_service.OCR_MAX_FILE_SIZE_BYTES + 1,
    }
    monkeypatch.setattr(
        evidence_service,
        "fetch_result_attachments",
        lambda *args: ([attachment], ""),
    )
    monkeypatch.setattr(
        evidence_service,
        "fetch_iteration_attachments",
        lambda *args: ([], ""),
    )
    session = FakeDownloadSession({})

    with caplog.at_level(logging.WARNING):
        response = evidence_service.fetch_attachment_details(
            session,
            {},
            "org",
            "project",
            passed_point(),
        )

    assert response["Evidence Uploaded"] == "Yes"
    assert session.calls == []
    assert "10 MB" in caplog.text


def test_actual_download_size_limit_is_enforced(monkeypatch, caplog):
    attachment = {
        "id": 1,
        "fileName": "large.pdf",
        "url": "https://ado/large",
        "size": 0,
    }
    monkeypatch.setattr(evidence_service, "OCR_MAX_FILE_SIZE_BYTES", 3)
    monkeypatch.setattr(
        evidence_service,
        "fetch_result_attachments",
        lambda *args: ([attachment], ""),
    )
    monkeypatch.setattr(
        evidence_service,
        "fetch_iteration_attachments",
        lambda *args: ([], ""),
    )
    ocr_calls = []
    monkeypatch.setattr(
        evidence_service,
        "extract_bytes_via_stream",
        lambda *args: ocr_calls.append(args),
    )
    session = FakeDownloadSession(
        {result_download_url(1): FakeDownloadResponse(b"1234")}
    )

    with caplog.at_level(logging.WARNING):
        response = evidence_service.fetch_attachment_details(
            session,
            {},
            "org",
            "project",
            passed_point(),
        )

    assert response["Evidence Uploaded"] == "Yes"
    assert ocr_calls == []
    assert "exceeds" in caplog.text


def test_ocr_failure_does_not_fail_evidence_metadata(monkeypatch, caplog):
    attachment = {
        "id": 1,
        "fileName": "evidence.pdf",
        "url": "https://ado/failure",
        "size": 10,
    }
    monkeypatch.setattr(
        evidence_service,
        "fetch_result_attachments",
        lambda *args: ([attachment], ""),
    )
    monkeypatch.setattr(
        evidence_service,
        "fetch_iteration_attachments",
        lambda *args: ([], ""),
    )
    monkeypatch.setattr(
        evidence_service,
        "extract_bytes_via_stream",
        lambda *args: (_ for _ in ()).throw(RuntimeError("OCR unavailable")),
    )
    session = FakeDownloadSession(
        {result_download_url(1): FakeDownloadResponse(b"evidence")}
    )

    with caplog.at_level(logging.WARNING):
        response = evidence_service.fetch_attachment_details(
            session,
            {},
            "org",
            "project",
            passed_point(),
        )

    assert response["Evidence Uploaded"] == "Yes"
    assert response["Evidence Count"] == 1
    assert "OCR unavailable" in caplog.text


def test_missing_ocr_content_does_not_fail_evidence_metadata(monkeypatch, caplog):
    attachment = {
        "id": 1,
        "fileName": "evidence.pdf",
        "url": "https://ado/invalid-response",
        "size": 10,
    }
    monkeypatch.setattr(
        evidence_service,
        "fetch_result_attachments",
        lambda *args: ([attachment], ""),
    )
    monkeypatch.setattr(
        evidence_service,
        "fetch_iteration_attachments",
        lambda *args: ([], ""),
    )
    monkeypatch.setattr(
        evidence_service,
        "extract_bytes_via_stream",
        lambda *args: {"data": {}},
    )
    session = FakeDownloadSession(
        {result_download_url(1): FakeDownloadResponse(b"evidence")}
    )

    with caplog.at_level(logging.WARNING):
        response = evidence_service.fetch_attachment_details(
            session,
            {},
            "org",
            "project",
            passed_point(),
        )

    assert response["Evidence Uploaded"] == "Yes"
    assert "data.content" in caplog.text


def test_iteration_lookup_collects_iteration_and_action_attachments():
    class IterationResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "value": [
                    {
                        "id": 7,
                        "attachments": [{"id": 1, "name": "iteration.pdf"}],
                        "actionResults": [
                            {"attachments": [{"id": 2, "name": "action.png"}]}
                        ],
                    }
                ]
            }

    session = FakeDownloadSession({"unused": IterationResponse()})
    session.get = lambda *args, **kwargs: IterationResponse()

    attachments, error = ado_service.fetch_iteration_attachments(
        session,
        {},
        "org",
        "project",
        "10",
        "20",
    )

    assert error == ""
    assert [item["name"] for item in attachments] == [
        "iteration.pdf",
        "action.png",
    ]
    assert [item["iterationId"] for item in attachments] == [7, 7]
