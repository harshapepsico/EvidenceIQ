"""Simple schema-like containers for dashboard data."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AttachmentStatus:
    uploaded: str = "N/A"
    count: int = 0
    files: str = ""
    size: int = 0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Evidence Uploaded": self.uploaded,
            "Evidence Count": self.count,
            "Evidence Files": self.files,
            "Evidence Size": self.size,
            "Evidence Error": self.error,
        }


@dataclass
class DashboardContext:
    project: str = ""
    plan_id: str = ""
    suite_ids: Optional[List[int]] = None
    records: List[Dict[str, Any]] = field(default_factory=list)
