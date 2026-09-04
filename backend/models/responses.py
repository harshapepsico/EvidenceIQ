"""Response helpers for service boundaries."""

from typing import Any, Dict


def evidence_response(uploaded: str = "N/A", count: int = 0, files: str = "", size: int = 0, error: str = "") -> Dict[str, Any]:
    return {
        "Evidence Uploaded": uploaded,
        "Evidence Count": count,
        "Evidence Files": files,
        "Evidence Size": size,
        "Evidence Error": error,
    }
