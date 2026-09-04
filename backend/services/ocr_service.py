"""OCR service placeholder for future provider integration."""


def extract_text_from_file(file_path: str) -> str:
    raise NotImplementedError("OCR integration will be added in a later step.")


import requests
import base64
import uuid
from pathlib import Path
from backend.config import settings

BASE_URL = "https://apim-na.qa.mypepsico.com/cgf/pepgenx"

COMMON_HEADERS = {
    "team_id":          settings.TEAM_ID,
    "project_id":       settings.PROJECT_ID,
    "user_id":          "81161059",
    "transaction_id":   str(uuid.uuid4()),
    "x-pepgenx-apikey": settings.DEVX_API_KEY,
    "correlationId":    str(uuid.uuid4()),
    "Authorization":    f"Bearer {settings.BEARER_TOKEN}",
    
}

# ── Method 1: File Stream Extraction (base64 JSON) ───────────────────────────

def extract_via_stream(file_path: str, model_name: str) -> dict:
    """Submit a file as base64 JSON for ADI extraction."""
    file_bytes = Path(file_path).read_bytes()
    b64_content = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "file_name":   Path(file_path).name,
        "file_stream": b64_content,
        "model_name":  model_name,
    }

    resp = requests.post(
        f"{BASE_URL}/v1/deaas/adi/file-stream-extraction",
        headers={**COMMON_HEADERS, "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


# ── Method 2: Multipart File Upload ──────────────────────────────────────────

def extract_via_upload(file_path: str, model_name: str, blob_container: str = "") -> dict:
    """Upload a file directly via multipart/form-data for ADI extraction."""
    upload_headers = dict(COMMON_HEADERS)
    if blob_container:
        upload_headers["x-blob-storage-container-name"] = blob_container

    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/v1/deaas/adi/file-extraction",
            headers=upload_headers,
            files={"file": (Path(file_path).name, f, "application/octet-stream")},
            data={"model_name": model_name},
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


# ── Usage ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    #Stream extraction — invoice with prebuilt-invoice model
    print("── Stream Extraction (prebuilt-invoice) ──")
    result = extract_via_stream("HarshaVardhan_Resume.pdf", "prebuilt-invoice")
    print(f"  Status : {result['status']}")
    print(f"  Pages  : {result['pages']}")
    print(f"  Content: {result['data']['content']}")

    # # Multipart upload — layout analysis with prebuilt-layout
    # print("\n── Multipart Upload (prebuilt-layout) ──")
    # result2 = extract_via_upload("HarshaVardhan_Resume.pdf", "prebuilt-layout")
    # # print(f" Content : {result2['content']}")
    # print(f"  Status : {result2['status']}")
    # print(f"  Pages  : {result2['pages']}")
    # tables = result2["data"].get("tables", [])
    # print(f"  Tables found: {len(tables)}")

    # # Pretty-print full response
    # print("\n── Full Response ──")
    # print(json.dumps(result2, indent=2))