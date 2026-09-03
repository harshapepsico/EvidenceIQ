import base64
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from evidenceiq.services import ocr_service


class FakeOCRResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"data": {"content": "extracted"}}


def test_extract_bytes_via_stream_sends_exact_content_and_fresh_ids(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeOCRResponse()

    monkeypatch.setattr(ocr_service.requests, "post", fake_post)

    first = ocr_service.extract_bytes_via_stream(
        "evidence.pdf",
        b"first payload",
        "prebuilt-layout",
    )
    ocr_service.extract_bytes_via_stream(
        "evidence.png",
        b"second payload",
        "prebuilt-layout",
    )

    assert first["data"]["content"] == "extracted"
    assert calls[0][1]["json"] == {
        "file_name": "evidence.pdf",
        "file_stream": base64.b64encode(b"first payload").decode("utf-8"),
        "model_name": "prebuilt-layout",
    }
    assert calls[0][1]["headers"]["Content-Type"] == "application/json"
    assert (
        calls[0][1]["headers"]["transaction_id"]
        != calls[1][1]["headers"]["transaction_id"]
    )
    assert (
        calls[0][1]["headers"]["correlationId"]
        != calls[1][1]["headers"]["correlationId"]
    )


def test_extract_bytes_via_stream_rejects_oversized_content(monkeypatch):
    monkeypatch.setattr(ocr_service, "OCR_MAX_FILE_SIZE_BYTES", 3)

    with pytest.raises(ValueError, match="exceeds"):
        ocr_service.extract_bytes_via_stream("large.pdf", b"1234", "prebuilt-layout")


def test_extract_bytes_via_stream_limits_concurrency_to_four(monkeypatch):
    active = 0
    maximum_active = 0
    lock = threading.Lock()

    def fake_post(url, **kwargs):
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return FakeOCRResponse()

    monkeypatch.setattr(ocr_service.requests, "post", fake_post)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(
                ocr_service.extract_bytes_via_stream,
                f"evidence-{index}.pdf",
                b"content",
                "prebuilt-layout",
            )
            for index in range(8)
        ]
        for future in futures:
            future.result()

    assert maximum_active == ocr_service.OCR_MAX_CONCURRENCY
