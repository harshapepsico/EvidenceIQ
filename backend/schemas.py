"""API request and response models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DashboardRequest(BaseModel):
    """Values needed to load an Azure DevOps test dashboard."""

    project: str = Field(..., min_length=1)
    plan_id: str = Field(..., min_length=1)
    suite_ids: Optional[str] = None


class DashboardResponse(BaseModel):
    """Dashboard data returned to the Streamlit client."""

    records: List[Dict[str, Any]]
    metrics: Dict[str, Any]
